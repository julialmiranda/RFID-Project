from flask import Flask, request, jsonify, Response
import psycopg2
import csv
import os
from datetime import datetime
from pubsub import AsyncConn
from flask_cors import CORS
from flask import Response


app = Flask(__name__)
CORS(app)
pubnub = AsyncConn("Flask Application", "meu_canal")

CSV_NAME = "relatorio_acessos.csv"

DB_CONFIG = {
    "host": "10.1.25.36",
    "database": "rfid_monitoramento",
    "user": "postgres",
    "password": "123456",
    "port": "5432"
}


def connect_db():
    return psycopg2.connect(**DB_CONFIG)


def montar_colaborador(row):
    return {
        "id": row[0],
        "nome": row[1],
        "matricula": row[2],
        "cargo": row[3],
        "tag_rfid": row[4],
        "acesso": row[5],
        "ativo": row[6]
    }


def montar_log(row):
    return {
        "id": row[0],
        "tipo": row[1],
        "nome": row[2],
        "matricula": row[3],
        "tag_rfid": row[4],
        "status": row[5],
        "mensagem": row[6],
        "timestamp": str(row[7]),
        "tempo_permanencia_minutos": float(row[8]) if len(row) > 8 and row[8] is not None else None
    }


def salvar_csv(evento):
    arquivo_existe = os.path.isfile(CSV_NAME)

    with open(CSV_NAME, "a", newline="", encoding="utf-8") as arquivo:
        campos = campos = ["tipo", "nome", "matricula", "tag_rfid", "status", "mensagem", "timestamp", "tempo_permanencia_minutos"]
        writer = csv.DictWriter(arquivo, fieldnames=campos)

        if not arquivo_existe:
            writer.writeheader()

        writer.writerow(evento)


def buscar_colaborador_por_tag(tag_rfid):
    with connect_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, nome, matricula, cargo, tag_rfid, acesso, ativo
                FROM colaboradores
                WHERE tag_rfid = %s
            """, (tag_rfid,))
            row = cursor.fetchone()

    if row:
        return montar_colaborador(row)

    return None


def buscar_ultimo_log_por_tag(tag_rfid):
    with connect_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT tipo
                FROM logs_acesso
                WHERE tag_rfid = %s
                ORDER BY id DESC
                LIMIT 1
            """, (tag_rfid,))
            return cursor.fetchone()


def ja_entrou_hoje(tag_rfid):
    hoje = datetime.now().strftime("%Y-%m-%d")

    with connect_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*)
                FROM logs_acesso
                WHERE tag_rfid = %s
                AND tipo = 'ENTRADA'
                AND DATE(timestamp) = %s
            """, (tag_rfid, hoje))
            total = cursor.fetchone()[0]

    return total > 0


def criar_evento_por_tag(tag_rfid):
    colaborador = buscar_colaborador_por_tag(tag_rfid)

    if colaborador is None:
        return {
            "tipo": "TENTATIVA_INVASAO",
            "nome": "Desconhecido",
            "matricula": None,
            "tag_rfid": tag_rfid,
            "status": "TAG_NAO_CADASTRADA",
            "mensagem": "Tentativa de invasão com tag desconhecida"
        }

    if colaborador["acesso"] is False or colaborador["ativo"] is False:
        return {
            "tipo": "TENTATIVA_NEGADA",
            "nome": colaborador["nome"],
            "matricula": colaborador["matricula"],
            "tag_rfid": tag_rfid,
            "status": "NAO_AUTORIZADO",
            "mensagem": f"Acesso negado para {colaborador['nome']}"
        }

    ultimo_log = buscar_ultimo_log_por_tag(tag_rfid)

    if ultimo_log and ultimo_log[0] == "ENTRADA":
        return {
            "tipo": "SAIDA",
            "nome": colaborador["nome"],
            "matricula": colaborador["matricula"],
            "tag_rfid": tag_rfid,
            "status": "SAIDA_REGISTRADA",
            "mensagem": f"Saída registrada para {colaborador['nome']}"
        }

    if ja_entrou_hoje(tag_rfid):
        mensagem = f"Bem-vindo de volta, {colaborador['nome']}"
    else:
        mensagem = f"Bem-vindo, {colaborador['nome']}"

    return {
        "tipo": "ENTRADA",
        "nome": colaborador["nome"],
        "matricula": colaborador["matricula"],
        "tag_rfid": tag_rfid,
        "status": "AUTORIZADO",
        "mensagem": mensagem
    }


@app.route("/", methods=["POST", "GET"])
def raiz():
    if request.method == "POST":
        return registrar_evento()
    

    return listar_logs()


def calcular_tempo_permanencia(tag_rfid, timestamp_saida):
    with connect_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT timestamp
                FROM logs_acesso
                WHERE tag_rfid = %s
                AND tipo = 'ENTRADA'
                ORDER BY id DESC
                LIMIT 1
            """, (tag_rfid,))

            row = cursor.fetchone()

    if not row:
        return None

    entrada = row[0]

    if isinstance(timestamp_saida, str):
        saida = datetime.strptime(timestamp_saida, "%Y-%m-%d %H:%M:%S")
    else:
        saida = timestamp_saida

    diferenca = saida - entrada
    minutos = round(diferenca.total_seconds() / 60, 2)

    return minutos


def registrar_evento():
    body = request.get_json()

    if not body:
        return jsonify({"error": "JSON não enviado"}), 400

    tag_rfid = body.get("tag_rfid")

    if not tag_rfid:
        return jsonify({"error": "Tag RFID não enviada"}), 400

    tag_rfid = str(tag_rfid)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    evento = criar_evento_por_tag(tag_rfid)
    evento["timestamp"] = timestamp
    evento["tempo_permanencia_minutos"] = None

    if evento["tipo"] == "SAIDA":
        evento["tempo_permanencia_minutos"] = calcular_tempo_permanencia(tag_rfid, timestamp)

    with connect_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO logs_acesso
                (tipo, nome, matricula, tag_rfid, status, mensagem, timestamp, tempo_permanencia_minutos)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                evento["tipo"],
                evento["nome"],
                evento["matricula"],
                evento["tag_rfid"],
                evento["status"],
                evento["mensagem"],
                evento["timestamp"],
                evento["tempo_permanencia_minutos"]
            ))
            conn.commit()

    salvar_csv(evento)
    pubnub.publish(evento)

    return jsonify({
        "message": "Evento registrado com sucesso",
        "evento": evento
    }), 201


@app.route("/logs", methods=["GET"])
def listar_logs():
    with connect_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, tipo, nome, matricula, tag_rfid, status, mensagem, timestamp
                FROM logs_acesso
                ORDER BY id DESC
            """)
            rows = cursor.fetchall()

    return jsonify([montar_log(row) for row in rows]), 200


@app.route("/logs/recentes", methods=["GET"])
def logs_recentes():
    with connect_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, tipo, nome, matricula, tag_rfid, status, mensagem, timestamp
                FROM logs_acesso
                ORDER BY id DESC
                LIMIT 10
            """)
            rows = cursor.fetchall()

    return jsonify([montar_log(row) for row in rows]), 200


@app.route("/logs/entradas", methods=["GET"])
def logs_entradas():
    return buscar_logs_por_tipo("ENTRADA")


@app.route("/logs/saidas", methods=["GET"])
def logs_saidas():
    return buscar_logs_por_tipo("SAIDA")


@app.route("/logs/negados", methods=["GET"])
def logs_negados():
    return buscar_logs_por_tipo("TENTATIVA_NEGADA")


@app.route("/logs/invasoes", methods=["GET"])
def logs_invasoes():
    return buscar_logs_por_tipo("TENTATIVA_INVASAO")


def buscar_logs_por_tipo(tipo):
    with connect_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, tipo, nome, matricula, tag_rfid, status, mensagem, timestamp
                FROM logs_acesso
                WHERE tipo = %s
                ORDER BY id DESC
            """, (tipo,))
            rows = cursor.fetchall()

    return jsonify([montar_log(row) for row in rows]), 200


@app.route("/colaboradores", methods=["POST"])
def criar_colaborador():
    body = request.get_json()

    if not body:
        return jsonify({"error": "JSON não enviado"}), 400

    nome = body.get("nome")
    matricula = body.get("matricula")
    cargo = body.get("cargo")
    tag_rfid = body.get("tag_rfid")
    acesso = body.get("acesso", True)
    ativo = body.get("ativo", True)

    if not nome or not tag_rfid:
        return jsonify({"error": "Nome e tag_rfid são obrigatórios"}), 400

    with connect_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO colaboradores
                (nome, matricula, cargo, tag_rfid, acesso, ativo)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (nome, matricula, cargo, tag_rfid, acesso, ativo))
            novo_id = cursor.fetchone()[0]
            conn.commit()

    return jsonify({
        "message": "Colaborador cadastrado com sucesso",
        "id": novo_id
    }), 201


@app.route("/colaboradores", methods=["GET"])
def listar_colaboradores():
    with connect_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, nome, matricula, cargo, tag_rfid, acesso, ativo
                FROM colaboradores
                ORDER BY id
            """)
            rows = cursor.fetchall()

    return jsonify([montar_colaborador(row) for row in rows]), 200


@app.route("/colaboradores/<int:id>", methods=["GET"])
def buscar_colaborador(id):
    with connect_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, nome, matricula, cargo, tag_rfid, acesso, ativo
                FROM colaboradores
                WHERE id = %s
            """, (id,))
            row = cursor.fetchone()

    if not row:
        return jsonify({"error": "Colaborador não encontrado"}), 404

    return jsonify(montar_colaborador(row)), 200


@app.route("/colaboradores/<int:id>", methods=["PUT"])
def editar_colaborador(id):
    body = request.get_json()

    if not body:
        return jsonify({"error": "JSON não enviado"}), 400

    with connect_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE colaboradores
                SET nome = COALESCE(%s, nome),
                    matricula = COALESCE(%s, matricula),
                    cargo = COALESCE(%s, cargo),
                    tag_rfid = COALESCE(%s, tag_rfid),
                    acesso = COALESCE(%s, acesso),
                    ativo = COALESCE(%s, ativo)
                WHERE id = %s
                RETURNING id
            """, (
                body.get("nome"),
                body.get("matricula"),
                body.get("cargo"),
                body.get("tag_rfid"),
                body.get("acesso"),
                body.get("ativo"),
                id
            ))

            atualizado = cursor.fetchone()
            conn.commit()

    if not atualizado:
        return jsonify({"error": "Colaborador não encontrado"}), 404

    return jsonify({"message": "Colaborador atualizado com sucesso"}), 200


@app.route("/colaboradores/<int:id>", methods=["DELETE"])
def excluir_colaborador(id):
    with connect_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                DELETE FROM colaboradores
                WHERE id = %s
                RETURNING id
            """, (id,))

            excluido = cursor.fetchone()
            conn.commit()

    if not excluido:
        return jsonify({"error": "Colaborador não encontrado"}), 404

    return jsonify({"message": "Colaborador excluído com sucesso"}), 200


@app.route("/login", methods=["POST"])
def login():
    body = request.get_json()

    if not body:
        return jsonify({"error": "JSON não enviado"}), 400

    usuario = body.get("usuario")
    senha = body.get("senha")

    with connect_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, usuario, perfil
                FROM usuarios_sistema
                WHERE usuario = %s AND senha = %s
            """, (usuario, senha))
            row = cursor.fetchone()

    if not row:
        return jsonify({"error": "Usuário ou senha inválidos"}), 401

    return jsonify({
        "message": "Login realizado com sucesso",
        "usuario": {
            "id": row[0],
            "usuario": row[1],
            "perfil": row[2]
        }
    }), 200

@app.route("/logs/export/csv", methods=["GET"])
def exportar_logs_csv():
    with connect_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT tipo, nome, matricula, tag_rfid, status, mensagem, timestamp
                FROM logs_acesso
                ORDER BY id DESC
            """)
            rows = cursor.fetchall()

    csv_content = "tipo,nome,matricula,tag_rfid,status,mensagem,timestamp\n"

    for row in rows:
        linha = [
            str(row[0] or ""),
            str(row[1] or ""),
            str(row[2] or ""),
            str(row[3] or ""),
            str(row[4] or ""),
            str(row[5] or ""),
            str(row[6] or "")
        ]

        linha_formatada = ",".join(
            '"' + campo.replace('"', '""') + '"'
            for campo in linha
        )

        csv_content += linha_formatada + "\n"

    return Response(
        csv_content,
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=logs_secureaccess.csv"
        }
    )
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
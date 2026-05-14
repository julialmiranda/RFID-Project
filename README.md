# 🔐 SecureAccess — Sistema de Controle de Acesso

Esse projeto consiste em um sistema de controle de acesso utilizando RFID, desenvolvido com Python, Flask e Raspberry Pi.
O projeto permite autenticação de usuários por tags RFID, gerenciamento de colaboradores, monitoramento em tempo real e exportação de relatórios de acesso.

---

## Estrutura do projeto

```
RFID-PROJECT/
│
├── app.py                  # API Flask principal
├── button.py               # Controle de botão físico
├── data.db                 # Banco de dados PostgreSQL
├── gerenciamento.html      # Página de gerenciamento
├── index.html              # Página de monitoramento em tempo real
├── login.html              # Tela de login
├── pubsub.py               # Comunicação via PubNub
├── relatorio_acessos.csv   # Relatório exportado automaticamente
├── tag.py                  # Leitura e validação de tags RFID
└── analise_acessos.ipynb   # Jupyter Notebook para análise de dados do relátorio CSV
```


---

# Tecnologias Utilizadas

| Tecnologia   | Finalidade           |
| ------------ | -------------------- |
| Python       | Backend e automações |
| Flask        | API e servidor web   |
| SQLite       | Banco de dados       |
| Raspberry Pi | Controle físico      |
| RFID MFRC522 | Leitura de tags      |
| HTML/CSS     | Interface web        |

---

## Endpoints da API

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | http://127.0.0.1:5000 | Cria eventos de entrada |
| GET | http://127.0.0.1:5000 | Consulta os eventos criados |
| POST | http://127.0.0.1:5000/colaboradores | Insere Colaborador |
| GET | http://127.0.0.1:5000/colaboradores | Consulta todos os colaboradores |
| POST | http://127.0.0.1:5000/login | Login |
| PUT | http://127.0.0.1:5000/colaboradores/3 | Adiciona novos colaboradores |
| DEL | http://127.0.0.1:5000/colaboradores/3 | Deleta colaboradores |

# Funcionalidades

O projeto possui diversas funcionalidades voltadas para controle e monitoramento de acesso utilizando RFID, entre elas:

- Controle de acesso utilizando tags RFID  
- Validação automática de permissões de entrada  
- Registro de acessos em tempo real  
- Gerenciamento completo de colaboradores  
- Associação de tags RFID aos usuários  
- Monitoramento contínuo do sistema  
- Histórico e auditoria de acessos  
- Exportação de relatórios em CSV  
- Interface web para administração  
- Sistema de autenticação/login  
- Integração com Raspberry Pi  
- Comunicação entre hardware e servidor Flask  
- Armazenamento de dados com SQLite  
- Atualização em tempo real dos acessos registrados

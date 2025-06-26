# Versão 0.0.1
# Monitoramento de servidores Windows via WinRM
# Coleta de métricas de CPU, RAM e Disco
# Armazenamento em Firestore e BigQuery

# Importando bibliotecas necessárias
import os
import winrm
import pytz
import logging
from flask import Flask, request, jsonify
from google.cloud import firestore
from datetime import datetime
from google.cloud import firestore, bigquery

# Inicialização do Flask e dos clientes do Firestore e BigQuery

# Inicia a aplicação Flask
app = Flask(__name__)

# Inicializa clientes para o Firestore
firestore_client = firestore.Client()

db = firestore.Client()

#Inicializa o cliente do BigQuery
bq_client = bigquery.Client()

# Rota princial de Post - coleta métricas dos servidores

@app.route('/', methods=['POST']) # Cria a rota POST / que receberá
def monitorar():
    # Este bloco extrai os parametros do JSON enviado na requisição, verifica se todos estão presentes, caso contrario retorna um erro 400
    data = request.json
    domain = data.get("domain")
    username = data.get("username")
    password = data.get("password")
    servers = data.get("servers") 

    if not all([domain, username, password, servers]):
        return jsonify({"success": False, "error": "Parâmetros ausentes"}), 400 

    # Loop para cada servidor
    resultados = []
    firestore_erro = ""
    bigquery_erro = ""

    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
    table_id = os.environ.get("BIGQUERY_TABLE_ID")

    db = None
    if project_id:
        try:
            db = firestore.Client(project=project_id)
        except Exception as e:
            firestore_erro = str(e)

    bq_client = None
    if table_id:
        try:
            bq_client = bigquery.Client()
        except Exception as e:
            bigquery_erro = str(e)

    for servidor in servidores:
        metricas = coletar_metricas(servidor, dominio, usuario, senha)

        if db:
            try:
                db.collection("metricas_servidor").add(metricas)
            except Exception as e:
                metricas["firestore_error"] = str(e) or firestore_erro

        if bq_client and table_id:
            try:
                row = {
                    "hostname": servidor,
                    "cpu": metricas.get("cpu"),
                    "ram": metricas.get("ram_gb_livre"),
                    "disco_livre": metricas.get("disco_gb_livre"),
                    "disco_total": metricas.get("disco_total_gb"),
                    "disco_percentual_livre": metricas.get("disco_percent_livre"),
                    "status": "OK" if metricas.get("success") else "ERRO",
                    "timestamp_utc": datetime.utcnow().isoformat(),
                    "timestamp_brasil": datetime.now(pytz.timezone("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M:%S")
                }
                errors = bq_client.insert_rows_json(table_id, [row])
                if errors:
                    metricas["bigquery_error"] = errors
            except Exception as e:
                metricas["bigquery_error"] = str(e) or bigquery_erro

        resultados.append(metricas)

    return json.dumps(resultados)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
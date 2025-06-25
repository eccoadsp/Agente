
import os
import json
from flask import Flask, request
import winrm
from datetime import datetime
import pytz
from google.cloud import firestore
from google.cloud import bigquery

app = Flask(__name__)

def coletar_metricas(hostname, dominio, usuario, senha):
    try:
        sessao = winrm.Session(
            target=hostname,
            auth=(f"{dominio}\\{usuario}", senha),
            transport='ntlm',
            server_cert_validation='ignore',
            read_timeout_sec=30,
            operation_timeout_sec=30
        )

        script = '''
        $cpu = Get-Counter '\\Processor(_Total)\\% Processor Time'
        $ram = Get-CimInstance Win32_OperatingSystem
        $disco = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'"
        $resultado = [PSCustomObject]@{
            cpu = [math]::Round($cpu.CounterSamples.CookedValue, 2)
            ram_gb_livre = [math]::Round($ram.FreePhysicalMemory / 1MB, 2)
            disco_total_gb = [math]::Round($disco.Size / 1GB, 2)
            disco_gb_livre = [math]::Round($disco.FreeSpace / 1GB, 2)
        }
        $resultado | ConvertTo-Json -Compress
        '''

        resultado = sessao.run_ps(script)
        if resultado.status_code != 0:
            return {"error": resultado.std_err.decode(), "success": False}

        dados = json.loads(resultado.std_out.decode())
        disco_total = dados["disco_total_gb"]
        disco_livre = dados["disco_gb_livre"]
        disco_percent_livre = round((disco_livre / disco_total) * 100, 2) if disco_total else 0

        utc_now = datetime.utcnow().replace(tzinfo=pytz.utc)
        brasil = utc_now.astimezone(pytz.timezone("America/Sao_Paulo"))

        return {
            "hostname": hostname,
            "cpu": dados["cpu"],
            "ram_gb_livre": dados["ram_gb_livre"],
            "disco_total_gb": disco_total,
            "disco_gb_livre": disco_livre,
            "disco_percent_livre": disco_percent_livre,
            "coletado_em_utc": utc_now.isoformat(),
            "coletado_em_brt": brasil.strftime("%d/%m/%Y %H:%M:%S"),
            "dominio": dominio,
            "usuario": usuario,
            "success": True
        }

    except Exception as e:
        return {"hostname": hostname, "error": str(e), "success": False}

@app.route("/", methods=["POST"])
def main():
    dados = request.get_json()
    dominio = dados.get("domain")
    usuario = dados.get("username")
    senha = dados.get("password")
    servidores = dados.get("servers", [])

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
    app.run(debug=True)

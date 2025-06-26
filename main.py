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
    for host in servers:
        try:
            full_username = f"{domain}\\{username}"
            target = f"https://{host}:5986/wsman"

            # Cria a sessão WinRM, configurando NTLM e ignorando a validação do certificado do servidor.
            session = winrm.Session(
                target=target,
                auth=(full_username, password),
                transport='ntlm',
                server_cert_validation='ignore'
            )

            # Executa o script PowerShell para coletar métricas de CPU, RAM e Disco.
            ps_script = """
            $cpu = (Get-Counter '\\Processor(_Total)\\% Processor Time').CounterSamples.CookedValue
            $mem = Get-WmiObject Win32_OperatingSystem
            $freeMemMB = [math]::Round($mem.FreePhysicalMemory / 1024, 2)

            $disco = Get-WmiObject Win32_LogicalDisk -Filter "DeviceID='C:'"
            $totalGB = [math]::Round($disco.Size / 1GB, 2)
            $livreGB = [math]::Round($disco.FreeSpace / 1GB, 2)
            $percentLivre = [math]::Round(($livreGB / $totalGB) * 100, 2)

            $obj = [PSCustomObject]@{
                CPU = [math]::Round($cpu, 2)
                RAM_Livre_GB = $freeMemMB / 1024
                Disco_Total_GB = $totalGB
                Disco_Livre_GB = $livreGB
                Disco_Livre_Porcentagem = $percentLivre
            }
            $obj | ConvertTo-Json -Depth 2
            """
            # Executa o script PowerShell e e interpreta o resultado JSON para um dicionário Python.
            result = session.run_ps(ps_script)
            output = result.std_out.decode("utf-8")
            metrics = eval(output) if output else {}
            
            # Timestamp para coleta.
            now_utc = datetime.utcnow().replace(tzinfo=pytz.utc)
            now_brt = now_utc.astimezone(pytz.timezone('America/Sao_Paulo'))

            # Cria estrutura de dados.
            # Prepara um dicionário com todos os dados coletados e informações de contexto.
            registro = {
                "servidor": host,
                "dominio": domain,
                "usuario": username,
                "coletado_em_utc": now_utc.isoformat(),
                "coletado_em_brt": now_brt.strftime('%d/%m/%Y %H:%M:%S'),
                "cpu": metrics.get("CPU"),
                "ram_gb_livre": metrics.get("RAM_Livre_GB"),
                "disco_total_gb": metrics.get("Disco_Total_GB"),
                "disco_gb_livre": metrics.get("Disco_Livre_GB"),
                "disco_percent_livre": metrics.get("Disco_Livre_Porcentagem")
            }

            # Grava no Firestore.
            # Tenta gravar o registro na coleção metricas do Firestore, em caso de erro, inclui a mensagem de erro no registro.
            try:
                db.collection("metricas").add(registro)
            except Exception as db_err:
                registro["firestore_error"] = str(db_err)

            # Grava no BigQuery.
            # Verifica se a variável BIGQUERY_TABLE_ID está definida, se sim, monta um row para o BigQuery
            # e envia com insert_rows_json. Em caso de erro, inclui a mensagem de erro no registro.
            
            try:
                table_id = os.environ.get("BIGQUERY_TABLE_ID")
                if table_id:
                    row = {
                        "servidor": host,
                        "dominio": domain,
                        "usuario": username,
                        "coletado_em_utc": now_utc.isoformat(),
                        "coletado_em_brt": now_brt.strftime('%Y-%m-%d %H:%M:%S'),
                        "cpu": metrics.get("CPU"),
                        "ram_gb_livre": metrics.get("RAM_Livre_GB"),
                        "disco_total_gb": metrics.get("Disco_Total_GB"),
                        "disco_gb_livre": metrics.get("Disco_Livre_GB"),
                        "disco_percent_livre": metrics.get("Disco_Livre_Porcentagem")
                    }
                    errors = bq_client.insert_rows_json(table_id, [row])
                    if errors:
                        registro["bigquery_error"] = errors
            except Exception as bq_err:
                registro["bigquery_exception"] = str(bq_err)

            # Adiciona o registro ao resultado final.
            resultados.append({"success": True, "hostname": host, "metrics": registro})

        # Tratamento de erro de conexão WinRM.
        # Se houver erro de conexão ou execução, armazena o erro completo no retorno para debugging.
        except Exception as e:
            import traceback
            erro_completo = traceback.format_exc()
            resultados.append({
                "success": False,
                "hostname": host,
                "error": str(e),
                "trace": erro_completo
            })

    # Retorna resultado final, envia todos os resultados (com sucesso ou erro) como resposta JSON.
    return jsonify(resultados)

# Rota GET de saúde - Verifica se o serviço está ativo.
@app.route('/', methods=['GET'])
def health():
    return 'OK', 200

# Inicializa a aplicação localmente (usado apenas fora do Cloud Run).
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
import winrm
import json
import getpass

# Entradas interativas
dominio = input("Digite o nome do domínio (ex: eccovalue): ").strip()
host = input("Digite o nome ou IP do servidor (ex: 172.210.225.172): ").strip()
usuario = input("Digite o nome do usuário (ex: eccoadmin): ").strip()
senha = getpass.getpass("Digite a senha para o usuário: ")

# Combina domínio + usuário
username = f"{dominio}\\{usuario}"

# Estabelece conexão via WinRM over HTTPS
session = winrm.Session(
    f'https://{host}:5986',
    auth=(username, senha),
    transport='ntlm',
    server_cert_validation='ignore'
)

# Script PowerShell remoto (métricas)
ps_script = """
$cpu = Get-Counter '\\Processor(_Total)\\% Processor Time' | Select -ExpandProperty CounterSamples | Select -ExpandProperty CookedValue;
$ram = Get-WmiObject Win32_OperatingSystem | Select -ExpandProperty FreePhysicalMemory;
$disk = Get-WmiObject Win32_LogicalDisk -Filter "DriveType=3" | Select DeviceID,FreeSpace,Size;
$result = [PSCustomObject]@{
  cpu_percent = [math]::Round($cpu, 2);
  free_ram_mb = [math]::Round($ram / 1024, 2);
  disks = $disk | ForEach-Object {
    @{
      drive = $_.DeviceID;
      free_gb = [math]::Round($_.FreeSpace / 1GB, 2);
      size_gb = [math]::Round($_.Size / 1GB, 2);
    }
  }
};
$result | ConvertTo-Json -Depth 3
"""

# Executa e imprime resultado
try:
    result = session.run_ps(ps_script)
    if result.status_code == 0:
        metrics = json.loads(result.std_out.decode('utf-8'))
        print(json.dumps(metrics, indent=2))
    else:
        print("Erro ao executar o script remoto:")
        print(result.std_err.decode('utf-8'))
except Exception as e:
    print(f"Erro de conexão: {e}")
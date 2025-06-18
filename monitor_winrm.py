import winrm
import json
import getpass

# Entrada interativa
host = input("Digite o IP ou nome do servidor (ex: 172.210.225.172): ").strip()
username = "eccovalue\\eccoadmin"
password = getpass.getpass("Digite a senha para o usuário eccovalue\\eccoadmin: ")

# Configurar sessão WinRM com segurança
session = winrm.Session(
    f'https://{host}:5986',
    auth=(username, password),
    transport='ntlm',
    server_cert_validation='ignore'  # Ignorar certificado autoassinado (seguro em ambiente de teste)
)

# Script PowerShell remoto
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

# Executar o script remoto
result = session.run_ps(ps_script)

# Verificar resultado
if result.status_code == 0:
    output = result.std_out.decode('utf-8')
    metrics = json.loads(output)
    print(json.dumps(metrics, indent=2))
else:
    print("Erro:")
    print(result.std_err.decode('utf-8'))

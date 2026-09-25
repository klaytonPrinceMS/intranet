# Vigia de arquivos — armadilha para o apagador (diagnostico temporario).
# Registra em logs\vigilancia_arquivos.log toda exclusao/renomeacao na raiz,
# com timestamp + snapshot dos processos no momento do evento.
$alvo = "C:\opencode"
$log = "C:\opencode\logs\vigilancia_arquivos.log"
$w = New-Object System.IO.FileSystemWatcher $alvo
$w.IncludeSubdirectories = $false
$w.EnableRaisingEvents = $true
$acao = {
    $n = $Event.SourceEventArgs.Name
    $tipo = $Event.SourceEventArgs.ChangeType
    $t = Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"
    $procs = (Get-Process | Sort-Object CPU -Descending | Select-Object -First 12 | ForEach-Object { "$($_.ProcessName):$($_.Id)" }) -join ","
    Add-Content $log "$t $tipo $n || $procs"
}
Register-ObjectEvent $w Deleted -Action $acao | Out-Null
Register-ObjectEvent $w Renamed -Action $acao | Out-Null
Add-Content $log "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') VIGIA INICIADO (raiz, sem subpastas)"
while ($true) { Start-Sleep -Seconds 60 }

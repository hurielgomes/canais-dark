$ErrorActionPreference = 'Stop'

$root = (Get-Location).Path
$editorialPath = Join-Path $root 'editorial_rules.py'
$animadoPath = Join-Path $root 'criar_animado.py'

if (!(Test-Path $editorialPath) -or !(Test-Path $animadoPath)) {
    throw 'Execute este script dentro da pasta raiz C:\canais-dark, onde editorial_rules.py e criar_animado.py existem.'
}


$editorial = Get-Content -Raw -Encoding UTF8 $editorialPath
$animado = Get-Content -Raw -Encoding UTF8 $animadoPath


$constant = @'
INSTRUCAO_FECHAMENTO_PADRAO = (
    "Termine com UMA pergunta específica sobre o ponto mais marcante deste vídeo, "
    "que só faça sentido para este tema. Não use perguntas genéricas como "
    "'já conhecia esse fato', 'o que mais te surpreendeu' ou 'conta nos comentários'."
)
'@


if ($editorial -notmatch 'INSTRUCAO_FECHAMENTO_PADRAO\s*=') {
    if ($editorial -notmatch '(?m)^ROOT\s*=\s*Path\(__file__\)\.resolve\(\)\.parent\s*$') {
        throw 'Não encontrei a linha ROOT esperada em editorial_rules.py. Nenhum arquivo foi alterado.'
    }
    $editorial = [regex]::Replace($editorial, '(?m)^(ROOT\s*=\s*Path\(__file__\)\.resolve\(\)\.parent\s*)$', ('$1' + "`r`n`r`n" + $constant.TrimEnd()), 1)
}


$replacement = @'
    fechamento = perfil_categoria(categoria).get(
        "closing_instruction",
        "Termine com UMA pergunta específica sobre o ponto mais marcante deste vídeo, "
        "que só faça sentido para este tema. Não use perguntas genéricas como "
        "'já conhecia esse fato', 'o que mais te surpreendeu' ou 'conta nos comentários'."
    )
'@

$pattern = '(?ms)^\s*fechamento\s*=\s*perfil_categoria\(categoria\)\.get\(\s*.*?\n\s*\)\s*(?=\n\s*return f"""|\n)'
if ($animado -match $pattern) {
    $animado = [regex]::Replace($animado, $pattern, $replacement.TrimEnd(), 1)
} elseif ($animado -notmatch '(?m)^\s*fechamento\s*=\s*perfil_categoria\(categoria\)\.get\(\s*"closing_instruction",') {
    throw 'Não encontrei o bloco fechamento esperado em criar_animado.py. Nenhum arquivo foi alterado.'
}


$backupEditorial = "$editorialPath.bak-antes-correcao"
$backupAnimado = "$animadoPath.bak-antes-correcao"
Copy-Item $editorialPath $backupEditorial -Force
Copy-Item $animadoPath $backupAnimado -Force
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($editorialPath, $editorial, $utf8NoBom)
[System.IO.File]::WriteAllText($animadoPath, $animado, $utf8NoBom)

Write-Host 'Correções aplicadas. Backups criados:'
Write-Host " - $backupEditorial"
Write-Host " - $backupAnimado"
Write-Host 'Agora execute: python -m compileall -q .'

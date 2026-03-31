# Week1 acceptance test script (Member A)
$baseUrl = "http://127.0.0.1:8000"
$pass = 0
$fail = 0

function Assert-True($name, $condition, $detail = "") {
    if ($condition) {
        Write-Host "[PASS] $name" -ForegroundColor Green
        $script:pass++
    }
    else {
        Write-Host "[FAIL] $name $detail" -ForegroundColor Red
        $script:fail++
    }
}

Write-Host "== 1) health check ==" -ForegroundColor Cyan
try {
    $health = Invoke-RestMethod -Uri "$baseUrl/health" -Method Get -TimeoutSec 5
    Assert-True "GET /health status=ok" ($health.status -eq "ok")
    Assert-True "GET /health has neo4j_connected" ($health.PSObject.Properties.Name -contains "neo4j_connected")
}
catch {
    Assert-True "GET /health reachable" $false $_.Exception.Message
}

Write-Host "`n== 2) /chat normal request ==" -ForegroundColor Cyan
$okBody = @{
    query = "beijing nursing home"
    history = @()
} | ConvertTo-Json -Depth 5

try {
    $resp = Invoke-WebRequest -Uri "$baseUrl/chat" -Method Post -ContentType "application/json" -Body $okBody -TimeoutSec 8
    $json = $resp.Content | ConvertFrom-Json

    Assert-True "POST /chat returns 200" ($resp.StatusCode -eq 200)
    Assert-True "has answer field" ($json.PSObject.Properties.Name -contains "answer")
    Assert-True "has context field" ($json.PSObject.Properties.Name -contains "context")
    Assert-True "has intent field" ($json.PSObject.Properties.Name -contains "intent")
    Assert-True "has rewritten_query field" ($json.PSObject.Properties.Name -contains "rewritten_query")
}
catch {
    Assert-True "POST /chat reachable" $false $_.Exception.Message
}

Write-Host "`n== 3) /chat empty query (expect 400) ==" -ForegroundColor Cyan
$badBody = @{
    query = "   "
    history = @()
} | ConvertTo-Json -Depth 5

try {
    Invoke-WebRequest -Uri "$baseUrl/chat" -Method Post -ContentType "application/json" -Body $badBody -TimeoutSec 8 | Out-Null
    Assert-True "empty query should not return 200" $false
}
catch {
    if ($_.Exception.Response) {
        $status = [int]$_.Exception.Response.StatusCode
        Assert-True "empty query returns 400" ($status -eq 400)
    }
    else {
        Assert-True "empty query got http response" $false $_.Exception.Message
    }
}

Write-Host "`n== 4) /chat missing query (expect 422) ==" -ForegroundColor Cyan
$invalidBody = @{
    history = @()
} | ConvertTo-Json -Depth 5

try {
    Invoke-WebRequest -Uri "$baseUrl/chat" -Method Post -ContentType "application/json" -Body $invalidBody -TimeoutSec 8 | Out-Null
    Assert-True "missing query should not return 200" $false
}
catch {
    if ($_.Exception.Response) {
        $status = [int]$_.Exception.Response.StatusCode
        Assert-True "missing query returns 422" ($status -eq 422)
    }
    else {
        Assert-True "missing query got http response" $false $_.Exception.Message
    }
}

Write-Host "`n==============================" -ForegroundColor Yellow
Write-Host ("TOTAL: PASS={0}, FAIL={1}" -f $pass, $fail) -ForegroundColor Yellow
Write-Host "==============================" -ForegroundColor Yellow

if ($fail -eq 0) {
    Write-Host "Result: Week1 checks passed." -ForegroundColor Green
}
else {
    Write-Host "Result: some checks failed, review FAIL items." -ForegroundColor Red
}
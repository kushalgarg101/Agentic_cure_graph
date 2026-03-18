$ErrorActionPreference = "Stop"
$base = "http://localhost:8000"
$files = @(
    "test_data/patient_parkinsons.json",
    "test_data/patient_alzheimers.json",
    "test_data/patient_lung_cancer.json"
)

foreach ($f in $files) {
    Write-Host "`n========== Testing: $f ==========" -ForegroundColor Cyan

    if (-not (Test-Path $f)) {
        Write-Host "  SKIP - file not found" -ForegroundColor Yellow
        continue
    }

    # Step 1: Normalize
    Write-Host "  [1/2] Normalizing FHIR..." -ForegroundColor Gray
    try {
        $normalized = Invoke-RestMethod -Method Post -Uri "$base/fhir/normalize" `
            -ContentType "application/json" -InFile $f
        Write-Host "  OK - Diagnoses: $($normalized.patient_case.diagnoses -join ', ')" -ForegroundColor Green
    } catch {
        Write-Host "  FAIL - $($_.Exception.Message)" -ForegroundColor Red
        continue
    }

    # Step 2: Analyze
    Write-Host "  [2/2] Running analysis..." -ForegroundColor Gray
    try {
        $body = $normalized | ConvertTo-Json -Depth 5
        $result = Invoke-RestMethod -Method Post -Uri "$base/analyze/local" `
            -ContentType "application/json" -Body $body
        Write-Host "  OK - Status: $($result.status) | Nodes: $($result.graph.nodes.Count) | Links: $($result.graph.links.Count)" -ForegroundColor Green
    } catch {
        Write-Host "  FAIL - $($_.Exception.Message)" -ForegroundColor Red
    }
}

Write-Host "`n========== Done ==========" -ForegroundColor Cyan

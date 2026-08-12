while ($true) {
    Write-Host "Starting a new scraping batch..."
    $output = python -u D:\多元大数据分析\analysis\43_amap_poi_unlimited_fetcher.py | Out-String
    Write-Host $output
    
    if ($output -match "All grids in the target area are already scraped") {
        Write-Host "All done!"
        break
    }
    
    if ($output -match "API LIMIT REACHED") {
        Write-Host "Quota exhausted. Stopping."
        break
    }
    
    Start-Sleep -Seconds 2
}

PS C:\Users\zhadr> Invoke-RestMethod -Method Post -Uri "https://growth-enrich-python-production.up.railway.app/price_on_date" -ContentType "application/json" -Body '{"ticker":"NVDA","date":"2020-03-23","eps":6.63}' | ConvertTo-Json -Depth 6

{
    "_errors":  {

                },
    "date":  "2020-03-23",
    "pe_same_share_basis":  31.91985358431372,
    "price_record":  {
                         "adjClose":  5.2907157316,
                         "adjHigh":  5.3849929079,
                         "adjLow":  4.9382335185,
                         "adjOpen":  5.1170865257,
                         "adjVolume":  643874640,
                         "close":  212.69,
                         "date":  "2020-03-23T00:00:00.000Z",
                         "divCash":  0.0,
                         "high":  216.48,
                         "low":  198.52,
                         "open":  205.71,
                         "splitFactor":  1.0,
                         "volume":  16096866
                     },
    "split_factor":  40.0,
    "ticker":  "NVDA"
}
PS C:\Users\zhadr>
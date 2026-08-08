PS C:\Users\zhadr> Invoke-RestMethod -Method Post -Uri "https://growth-enrich-python-production.up.railway.app/edgar_facts" -ContentType "application/json" -Body '{"ticker":"NVDA","as_of":"2020-03-23"}' | ConvertTo-Json -Depth 6
{
    "_cik":  "0001045810",
    "_entity_name":  "NVIDIA CORP",
    "_errors":  {

                },
    "_field_sources":  {
                           "capex":  [
                                         "PaymentsToAcquireProductiveAssets",
                                         "PaymentsToAcquirePropertyPlantAndEquipment"
                                     ],
                           "cash":  "CashAndCashEquivalentsAtCarryingValue",
                           "dividends_paid":  [
                                                  "PaymentsOfDividends"
                                              ],
                           "dps":  [
                                       "CommonStockDividendsPerShareCashPaid",
                                       "CommonStockDividendsPerShareDeclared"
                                   ],
                           "gross_profit":  [
                                                "GrossProfit"
                                            ],
                           "net_income":  [
                                              "NetIncomeLoss"
                                          ],
                           "ocf":  [
                                       "NetCashProvidedByUsedInOperatingActivities"
                                   ],
                           "operating_income":  [
                                                    "OperatingIncomeLoss"
                                                ],
                           "revenue":  [
                                           "Revenues"
                                       ],
                           "rpo":  "RevenueRemainingPerformanceObligation",
                           "sbc":  [
                                       "ShareBasedCompensation"
                                   ],
                           "shares_current":  "dei:EntityCommonStockSharesOutstanding (companyfacts)",
                           "shares_diluted":  [
                                                  "WeightedAverageNumberOfDilutedSharesOutstanding"
                                              ],
                           "short_term_investments":  "MarketableSecuritiesCurrent",
                           "total_debt":  "LongTermDebt"
                       },
    "_flags":  {
                   "confirmed_splits":  [
                                            {
                                                "earliest_filed":  "2020-02-20",
                                                "earliest_val":  618000000,
                                                "end":  "2020-01-26",
                                                "factor":  4,
                                                "latest_filed":  "2022-03-18",
                                                "latest_val":  2472000000,
                                                "tag":  "WeightedAverageNumberOfDilutedSharesOutstanding"
                                            },
                                            {
                                                "earliest_filed":  "2021-02-26",
                                                "earliest_val":  628000000,
                                                "end":  "2021-01-31",
                                                "factor":  4,
                                                "latest_filed":  "2023-02-24",
                                                "latest_val":  2510000000,
                                                "tag":  "WeightedAverageNumberOfDilutedSharesOutstanding"
                                            },
                                            {
                                                "earliest_filed":  "2023-02-24",
                                                "earliest_val":  2507000000,
                                                "end":  "2023-01-29",
                                                "factor":  10,
                                                "latest_filed":  "2025-02-26",
                                                "latest_val":  25070000000,
                                                "tag":  "WeightedAverageNumberOfDilutedSharesOutstanding"
                                            },
                                            {
                                                "earliest_filed":  "2024-02-21",
                                                "earliest_val":  2494000000,
                                                "end":  "2024-01-28",
                                                "factor":  10,
                                                "latest_filed":  "2026-02-25",
                                                "latest_val":  24940000000,
                                                "tag":  "WeightedAverageNumberOfDilutedSharesOutstanding"
                                            }
                                        ],
                   "long_term_debt_full_vs_noncurrent":  "using full LongTermDebt LongTermDebt; noncurrent-only LongTermDebtNoncurrent would understate",
                   "margin_step_business_event":  [
                                                      {
                                                          "cosignal_changed":  [
                                                                                   "accession"
                                                                               ],
                                                          "end":  "2012-01-29",
                                                          "in_cagr_window_3y":  false,
                                                          "in_cagr_window_5y":  false,
                                                          "jump_pct":  124.7,
                                                          "prev_end":  "2011-01-30",
                                                          "prev_ratio":  0.0722,
                                                          "prev_tag":  "Revenues",
                                                          "provenance_changed":  [

                                                                                 ],
                                                          "provenance_uncomparable":  [

                                                                                      ],
                                                          "ratio":  0.1622,
                                                          "tag":  "Revenues"
                                                      },
                                                      {
                                                          "cosignal_changed":  [
                                                                                   "accession"
                                                                               ],
                                                          "end":  "2015-01-25",
                                                          "in_cagr_window_3y":  false,
                                                          "in_cagr_window_5y":  false,
                                                          "jump_pct":  35.0,
                                                          "prev_end":  "2014-01-26",
                                                          "prev_ratio":  0.1201,
                                                          "prev_tag":  "Revenues",
                                                          "provenance_changed":  [

                                                                                 ],
                                                          "provenance_uncomparable":  [

                                                                                      ],
                                                          "ratio":  0.1621,
                                                          "tag":  "Revenues"
                                                      },
                                                      {
                                                          "cosignal_changed":  [

                                                                               ],
                                                          "end":  "2017-01-29",
                                                          "in_cagr_window_3y":  false,
                                                          "in_cagr_window_5y":  false,
                                                          "jump_pct":  87.7,
                                                          "prev_end":  "2016-01-31",
                                                          "prev_ratio":  0.1491,
                                                          "prev_tag":  "Revenues",
                                                          "provenance_changed":  [

                                                                                 ],
                                                          "provenance_uncomparable":  [

                                                                                      ],
                                                          "ratio":  0.2799,
                                                          "tag":  "Revenues"
                                                      },
                                                      {
                                                          "cosignal_changed":  [
                                                                                   "accession"
                                                                               ],
                                                          "end":  "2022-01-30",
                                                          "in_cagr_window_3y":  false,
                                                          "in_cagr_window_5y":  true,
                                                          "jump_pct":  37.3,
                                                          "prev_end":  "2021-01-31",
                                                          "prev_ratio":  0.2718,
                                                          "prev_tag":  "Revenues",
                                                          "provenance_changed":  [

                                                                                 ],
                                                          "provenance_uncomparable":  [

                                                                                      ],
                                                          "ratio":  0.3731,
                                                          "tag":  "Revenues"
                                                      },
                                                      {
                                                          "cosignal_changed":  [
                                                                                   "accession"
                                                                               ],
                                                          "end":  "2023-01-29",
                                                          "in_cagr_window_3y":  false,
                                                          "in_cagr_window_5y":  true,
                                                          "jump_pct":  58.0,
                                                          "prev_end":  "2022-01-30",
                                                          "prev_ratio":  0.3731,
                                                          "prev_tag":  "Revenues",
                                                          "provenance_changed":  [

                                                                                 ],
                                                          "provenance_uncomparable":  [

                                                                                      ],
                                                          "ratio":  0.1566,
                                                          "tag":  "Revenues"
                                                      },
                                                      {
                                                          "cosignal_changed":  [
                                                                                   "accession"
                                                                               ],
                                                          "end":  "2024-01-28",
                                                          "in_cagr_window_3y":  true,
                                                          "in_cagr_window_5y":  true,
                                                          "jump_pct":  245.6,
                                                          "prev_end":  "2023-01-29",
                                                          "prev_ratio":  0.1566,
                                                          "prev_tag":  "Revenues",
                                                          "provenance_changed":  [

                                                                                 ],
                                                          "provenance_uncomparable":  [

                                                                                      ],
                                                          "ratio":  0.5412,
                                                          "tag":  "Revenues"
                                                      }
                                                  ],
                   "series_tag_mixed":  {
                                            "capex":  {
                                                          "2010":  "PaymentsToAcquirePropertyPlantAndEquipment",
                                                          "2011":  "PaymentsToAcquirePropertyPlantAndEquipment",
                                                          "2012":  "PaymentsToAcquirePropertyPlantAndEquipment",
                                                          "2022":  "PaymentsToAcquireProductiveAssets",
                                                          "2023":  "PaymentsToAcquireProductiveAssets",
                                                          "2024":  "PaymentsToAcquireProductiveAssets",
                                                          "2025":  "PaymentsToAcquireProductiveAssets",
                                                          "2026":  "PaymentsToAcquireProductiveAssets"
                                                      },
                                            "dps":  {
                                                        "2011":  "CommonStockDividendsPerShareDeclared",
                                                        "2012":  "CommonStockDividendsPerShareDeclared",
                                                        "2013":  "CommonStockDividendsPerShareDeclared",
                                                        "2014":  "CommonStockDividendsPerShareDeclared",
                                                        "2015":  "CommonStockDividendsPerShareDeclared",
                                                        "2016":  "CommonStockDividendsPerShareDeclared",
                                                        "2017":  "CommonStockDividendsPerShareCashPaid",
                                                        "2018":  "CommonStockDividendsPerShareCashPaid",
                                                        "2019":  "CommonStockDividendsPerShareCashPaid",
                                                        "2020":  "CommonStockDividendsPerShareCashPaid",
                                                        "2021":  "CommonStockDividendsPerShareCashPaid",
                                                        "2022":  "CommonStockDividendsPerShareDeclared",
                                                        "2023":  "CommonStockDividendsPerShareDeclared",
                                                        "2024":  "CommonStockDividendsPerShareDeclared",
                                                        "2025":  "CommonStockDividendsPerShareDeclared",
                                                        "2026":  "CommonStockDividendsPerShareDeclared"
                                                    }
                                        },
                   "tag_conflict":  {
                                        "dps":  [
                                                    {
                                                        "end":  "2016-01-31",
                                                        "spread_pct":  70.9,
                                                        "values":  {
                                                                       "CommonStockDividendsPerShareCashPaid":  0.395,
                                                                       "CommonStockDividendsPerShareDeclared":  0.115
                                                                   }
                                                    },
                                                    {
                                                        "end":  "2023-01-29",
                                                        "spread_pct":  90.0,
                                                        "values":  {
                                                                       "CommonStockDividendsPerShareCashPaid":  0.16,
                                                                       "CommonStockDividendsPerShareDeclared":  0.016
                                                                   }
                                                    },
                                                    {
                                                        "end":  "2024-01-28",
                                                        "spread_pct":  90.0,
                                                        "values":  {
                                                                       "CommonStockDividendsPerShareCashPaid":  0.16,
                                                                       "CommonStockDividendsPerShareDeclared":  0.016
                                                                   }
                                                    }
                                                ],
                                        "revenue":  [
                                                        {
                                                            "absent_years":  [
                                                                                 "2019"
                                                                             ],
                                                            "chosen_tag":  "Revenues",
                                                            "note":  "single-tag series chosen on window coverage; years outside the anchor windows are absent by construction"
                                                        }
                                                    ],
                                        "shares_diluted":  [
                                                               {
                                                                   "end":  "2008-01-27",
                                                                   "spread_pct":  9.3,
                                                                   "values":  {
                                                                                  "WeightedAverageNumberOfDilutedSharesOutstanding":  606732,
                                                                                  "WeightedAverageNumberOfSharesOutstandingBasic":  550108
                                                                              }
                                                               },
                                                               {
                                                                   "end":  "2017-01-29",
                                                                   "spread_pct":  16.6,
                                                                   "values":  {
                                                                                  "WeightedAverageNumberOfDilutedSharesOutstanding":  649000000,
                                                                                  "WeightedAverageNumberOfSharesOutstandingBasic":  541000000
                                                                              }
                                                               },
                                                               {
                                                                   "end":  "2018-01-28",
                                                                   "spread_pct":  5.2,
                                                                   "values":  {
                                                                                  "WeightedAverageNumberOfDilutedSharesOutstanding":  632000000,
                                                                                  "WeightedAverageNumberOfSharesOutstandingBasic":  599000000
                                                                              }
                                                               }
                                                           ]
                                    },
                   "total_debt_computed":  "LongTermDebt"
               },
    "_missing":  [

                 ],
    "_source":  "sec_edgar",
    "_ticker":  "NVDA",
    "capex":  [
                  {
                      "end":  "2010-01-31",
                      "val":  77601000
                  },
                  {
                      "end":  "2011-01-30",
                      "val":  97890000
                  },
                  {
                      "end":  "2012-01-29",
                      "val":  138735000
                  },
                  {
                      "end":  "2022-01-30",
                      "val":  976000000
                  },
                  {
                      "end":  "2023-01-29",
                      "val":  1833000000
                  },
                  {
                      "end":  "2024-01-28",
                      "val":  1069000000
                  },
                  {
                      "end":  "2025-01-26",
                      "val":  3236000000
                  },
                  {
                      "end":  "2026-01-25",
                      "val":  6042000000
                  }
              ],
    "capex_audit":  [
                        {
                            "accn":  "0001045810-12-000013",
                            "end":  "2010-01-31",
                            "filed":  "2012-03-13",
                            "form":  "10-K",
                            "tag":  "PaymentsToAcquirePropertyPlantAndEquipment",
                            "unit":  "USD",
                            "val":  77601000
                        },
                        {
                            "accn":  "0001045810-12-000013",
                            "end":  "2011-01-30",
                            "filed":  "2012-03-13",
                            "form":  "10-K",
                            "tag":  "PaymentsToAcquirePropertyPlantAndEquipment",
                            "unit":  "USD",
                            "val":  97890000
                        },
                        {
                            "accn":  "0001045810-12-000013",
                            "end":  "2012-01-29",
                            "filed":  "2012-03-13",
                            "form":  "10-K",
                            "tag":  "PaymentsToAcquirePropertyPlantAndEquipment",
                            "unit":  "USD",
                            "val":  138735000
                        },
                        {
                            "accn":  "0001045810-24-000029",
                            "end":  "2022-01-30",
                            "filed":  "2024-02-21",
                            "form":  "10-K",
                            "tag":  "PaymentsToAcquireProductiveAssets",
                            "unit":  "USD",
                            "val":  976000000
                        },
                        {
                            "accn":  "0001045810-25-000023",
                            "end":  "2023-01-29",
                            "filed":  "2025-02-26",
                            "form":  "10-K",
                            "tag":  "PaymentsToAcquireProductiveAssets",
                            "unit":  "USD",
                            "val":  1833000000
                        },
                        {
                            "accn":  "0001045810-26-000021",
                            "end":  "2024-01-28",
                            "filed":  "2026-02-25",
                            "form":  "10-K",
                            "tag":  "PaymentsToAcquireProductiveAssets",
                            "unit":  "USD",
                            "val":  1069000000
                        },
                        {
                            "accn":  "0001045810-26-000021",
                            "end":  "2025-01-26",
                            "filed":  "2026-02-25",
                            "form":  "10-K",
                            "tag":  "PaymentsToAcquireProductiveAssets",
                            "unit":  "USD",
                            "val":  3236000000
                        },
                        {
                            "accn":  "0001045810-26-000021",
                            "end":  "2026-01-25",
                            "filed":  "2026-02-25",
                            "form":  "10-K",
                            "tag":  "PaymentsToAcquireProductiveAssets",
                            "unit":  "USD",
                            "val":  6042000000
                        }
                    ],
    "cash":  13237000000,
    "cash_audit":  {
                       "accn":  "0001045810-26-000052",
                       "end":  "2026-04-26",
                       "filed":  "2026-05-20",
                       "val":  13237000000
                   },
    "current_portion_debt":  1000000000,
    "current_portion_debt_audit":  {
                                       "accn":  "0001045810-26-000052",
                                       "end":  "2026-04-26",
                                       "filed":  "2026-05-20",
                                       "val":  1000000000
                                   },
    "debt_components_tags":  {
                                 "components_complete":  true,
                                 "current_maturities":  "LongTermDebtCurrent",
                                 "full_long_term_debt":  "LongTermDebt",
                                 "noncurrent":  "LongTermDebtNoncurrent"
                             },
    "dividends_paid":  [
                           {
                               "end":  "2011-01-30",
                               "val":  0
                           },
                           {
                               "end":  "2012-01-29",
                               "val":  0
                           },
                           {
                               "end":  "2013-01-27",
                               "val":  46866000
                           },
                           {
                               "end":  "2014-01-26",
                               "val":  181000000
                           },
                           {
                               "end":  "2015-01-25",
                               "val":  186000000
                           },
                           {
                               "end":  "2016-01-31",
                               "val":  213000000
                           },
                           {
                               "end":  "2017-01-29",
                               "val":  261000000
                           },
                           {
                               "end":  "2018-01-28",
                               "val":  341000000
                           },
                           {
                               "end":  "2019-01-27",
                               "val":  371000000
                           },
                           {
                               "end":  "2020-01-26",
                               "val":  390000000
                           },
                           {
                               "end":  "2021-01-31",
                               "val":  395000000
                           },
                           {
                               "end":  "2022-01-30",
                               "val":  399000000
                           },
                           {
                               "end":  "2023-01-29",
                               "val":  398000000
                           },
                           {
                               "end":  "2024-01-28",
                               "val":  395000000
                           },
                           {
                               "end":  "2025-01-26",
                               "val":  834000000
                           },
                           {
                               "end":  "2026-01-25",
                               "val":  974000000
                           }
                       ],
    "dividends_paid_audit":  [
                                 {
                                     "accn":  "0001045810-13-000008",
                                     "end":  "2011-01-30",
                                     "filed":  "2013-03-12",
                                     "form":  "10-K",
                                     "tag":  "PaymentsOfDividends",
                                     "unit":  "USD",
                                     "val":  0
                                 },
                                 {
                                     "accn":  "0001045810-14-000030",
                                     "end":  "2012-01-29",
                                     "filed":  "2014-03-13",
                                     "form":  "10-K",
                                     "tag":  "PaymentsOfDividends",
                                     "unit":  "USD",
                                     "val":  0
                                 },
                                 {
                                     "accn":  "0001045810-15-000036",
                                     "end":  "2013-01-27",
                                     "filed":  "2015-03-12",
                                     "form":  "10-K",
                                     "tag":  "PaymentsOfDividends",
                                     "unit":  "USD",
                                     "val":  46866000
                                 },
                                 {
                                     "accn":  "0001045810-16-000205",
                                     "end":  "2014-01-26",
                                     "filed":  "2016-03-17",
                                     "form":  "10-K",
                                     "tag":  "PaymentsOfDividends",
                                     "unit":  "USD",
                                     "val":  181000000
                                 },
                                 {
                                     "accn":  "0001045810-17-000027",
                                     "end":  "2015-01-25",
                                     "filed":  "2017-03-01",
                                     "form":  "10-K",
                                     "tag":  "PaymentsOfDividends",
                                     "unit":  "USD",
                                     "val":  186000000
                                 },
                                 {
                                     "accn":  "0001045810-18-000010",
                                     "end":  "2016-01-31",
                                     "filed":  "2018-02-28",
                                     "form":  "10-K",
                                     "tag":  "PaymentsOfDividends",
                                     "unit":  "USD",
                                     "val":  213000000
                                 },
                                 {
                                     "accn":  "0001045810-19-000023",
                                     "end":  "2017-01-29",
                                     "filed":  "2019-02-21",
                                     "form":  "10-K",
                                     "tag":  "PaymentsOfDividends",
                                     "unit":  "USD",
                                     "val":  261000000
                                 },
                                 {
                                     "accn":  "0001045810-20-000010",
                                     "end":  "2018-01-28",
                                     "filed":  "2020-02-20",
                                     "form":  "10-K",
                                     "tag":  "PaymentsOfDividends",
                                     "unit":  "USD",
                                     "val":  341000000
                                 },
                                 {
                                     "accn":  "0001045810-21-000010",
                                     "end":  "2019-01-27",
                                     "filed":  "2021-02-26",
                                     "form":  "10-K",
                                     "tag":  "PaymentsOfDividends",
                                     "unit":  "USD",
                                     "val":  371000000
                                 },
                                 {
                                     "accn":  "0001045810-22-000036",
                                     "end":  "2020-01-26",
                                     "filed":  "2022-03-18",
                                     "form":  "10-K",
                                     "tag":  "PaymentsOfDividends",
                                     "unit":  "USD",
                                     "val":  390000000
                                 },
                                 {
                                     "accn":  "0001045810-23-000017",
                                     "end":  "2021-01-31",
                                     "filed":  "2023-02-24",
                                     "form":  "10-K",
                                     "tag":  "PaymentsOfDividends",
                                     "unit":  "USD",
                                     "val":  395000000
                                 },
                                 {
                                     "accn":  "0001045810-24-000029",
                                     "end":  "2022-01-30",
                                     "filed":  "2024-02-21",
                                     "form":  "10-K",
                                     "tag":  "PaymentsOfDividends",
                                     "unit":  "USD",
                                     "val":  399000000
                                 },
                                 {
                                     "accn":  "0001045810-25-000023",
                                     "end":  "2023-01-29",
                                     "filed":  "2025-02-26",
                                     "form":  "10-K",
                                     "tag":  "PaymentsOfDividends",
                                     "unit":  "USD",
                                     "val":  398000000
                                 },
                                 {
                                     "accn":  "0001045810-26-000021",
                                     "end":  "2024-01-28",
                                     "filed":  "2026-02-25",
                                     "form":  "10-K",
                                     "tag":  "PaymentsOfDividends",
                                     "unit":  "USD",
                                     "val":  395000000
                                 },
                                 {
                                     "accn":  "0001045810-26-000021",
                                     "end":  "2025-01-26",
                                     "filed":  "2026-02-25",
                                     "form":  "10-K",
                                     "tag":  "PaymentsOfDividends",
                                     "unit":  "USD",
                                     "val":  834000000
                                 },
                                 {
                                     "accn":  "0001045810-26-000021",
                                     "end":  "2026-01-25",
                                     "filed":  "2026-02-25",
                                     "form":  "10-K",
                                     "tag":  "PaymentsOfDividends",
                                     "unit":  "USD",
                                     "val":  974000000
                                 }
                             ],
    "dps":  [
                {
                    "end":  "2011-01-30",
                    "val":  0
                },
                {
                    "end":  "2012-01-29",
                    "val":  0
                },
                {
                    "end":  "2013-01-27",
                    "val":  0.075
                },
                {
                    "end":  "2014-01-26",
                    "val":  0.31
                },
                {
                    "end":  "2015-01-25",
                    "val":  0.34
                },
                {
                    "end":  "2016-01-31",
                    "val":  0.115
                },
                {
                    "end":  "2017-01-29",
                    "val":  0.485
                },
                {
                    "end":  "2018-01-28",
                    "val":  0.57
                },
                {
                    "end":  "2019-01-27",
                    "val":  0.61
                },
                {
                    "end":  "2020-01-26",
                    "val":  0.16
                },
                {
                    "end":  "2021-01-31",
                    "val":  0.16
                },
                {
                    "end":  "2022-01-30",
                    "val":  0.16
                },
                {
                    "end":  "2023-01-29",
                    "val":  0.016
                },
                {
                    "end":  "2024-01-28",
                    "val":  0.016
                },
                {
                    "end":  "2025-01-26",
                    "val":  0.034
                },
                {
                    "end":  "2026-01-25",
                    "val":  0.04
                }
            ],
    "dps_audit":  [
                      {
                          "accn":  "0001045810-13-000008",
                          "end":  "2011-01-30",
                          "filed":  "2013-03-12",
                          "form":  "10-K",
                          "tag":  "CommonStockDividendsPerShareDeclared",
                          "unit":  "USD/shares",
                          "val":  0
                      },
                      {
                          "accn":  "0001045810-14-000030",
                          "end":  "2012-01-29",
                          "filed":  "2014-03-13",
                          "form":  "10-K",
                          "tag":  "CommonStockDividendsPerShareDeclared",
                          "unit":  "USD/shares",
                          "val":  0
                      },
                      {
                          "accn":  "0001045810-15-000036",
                          "end":  "2013-01-27",
                          "filed":  "2015-03-12",
                          "form":  "10-K",
                          "tag":  "CommonStockDividendsPerShareDeclared",
                          "unit":  "USD/shares",
                          "val":  0.075
                      },
                      {
                          "accn":  "0001045810-15-000036",
                          "end":  "2014-01-26",
                          "filed":  "2015-03-12",
                          "form":  "10-K",
                          "tag":  "CommonStockDividendsPerShareDeclared",
                          "unit":  "USD/shares",
                          "val":  0.31
                      },
                      {
                          "accn":  "0001045810-15-000036",
                          "end":  "2015-01-25",
                          "filed":  "2015-03-12",
                          "form":  "10-K",
                          "tag":  "CommonStockDividendsPerShareDeclared",
                          "unit":  "USD/shares",
                          "val":  0.34
                      },
                      {
                          "accn":  "0001045810-16-000205",
                          "end":  "2016-01-31",
                          "filed":  "2016-03-17",
                          "form":  "10-K",
                          "tag":  "CommonStockDividendsPerShareDeclared",
                          "unit":  "USD/shares",
                          "val":  0.115
                      },
                      {
                          "accn":  "0001045810-19-000023",
                          "end":  "2017-01-29",
                          "filed":  "2019-02-21",
                          "form":  "10-K",
                          "tag":  "CommonStockDividendsPerShareCashPaid",
                          "unit":  "USD/shares",
                          "val":  0.485
                      },
                      {
                          "accn":  "0001045810-20-000010",
                          "end":  "2018-01-28",
                          "filed":  "2020-02-20",
                          "form":  "10-K",
                          "tag":  "CommonStockDividendsPerShareCashPaid",
                          "unit":  "USD/shares",
                          "val":  0.57
                      },
                      {
                          "accn":  "0001045810-21-000010",
                          "end":  "2019-01-27",
                          "filed":  "2021-02-26",
                          "form":  "10-K",
                          "tag":  "CommonStockDividendsPerShareCashPaid",
                          "unit":  "USD/shares",
                          "val":  0.61
                      },
                      {
                          "accn":  "0001045810-22-000036",
                          "end":  "2020-01-26",
                          "filed":  "2022-03-18",
                          "form":  "10-K",
                          "tag":  "CommonStockDividendsPerShareCashPaid",
                          "unit":  "USD/shares",
                          "val":  0.16
                      },
                      {
                          "accn":  "0001045810-23-000017",
                          "end":  "2021-01-31",
                          "filed":  "2023-02-24",
                          "form":  "10-K",
                          "tag":  "CommonStockDividendsPerShareCashPaid",
                          "unit":  "USD/shares",
                          "val":  0.16
                      },
                      {
                          "accn":  "0001045810-24-000029",
                          "end":  "2022-01-30",
                          "filed":  "2024-02-21",
                          "form":  "10-K",
                          "tag":  "CommonStockDividendsPerShareDeclared",
                          "unit":  "USD/shares",
                          "val":  0.16
                      },
                      {
                          "accn":  "0001045810-25-000023",
                          "end":  "2023-01-29",
                          "filed":  "2025-02-26",
                          "form":  "10-K",
                          "tag":  "CommonStockDividendsPerShareDeclared",
                          "unit":  "USD/shares",
                          "val":  0.016
                      },
                      {
                          "accn":  "0001045810-26-000021",
                          "end":  "2024-01-28",
                          "filed":  "2026-02-25",
                          "form":  "10-K",
                          "tag":  "CommonStockDividendsPerShareDeclared",
                          "unit":  "USD/shares",
                          "val":  0.016
                      },
                      {
                          "accn":  "0001045810-26-000021",
                          "end":  "2025-01-26",
                          "filed":  "2026-02-25",
                          "form":  "10-K",
                          "tag":  "CommonStockDividendsPerShareDeclared",
                          "unit":  "USD/shares",
                          "val":  0.034
                      },
                      {
                          "accn":  "0001045810-26-000021",
                          "end":  "2026-01-25",
                          "filed":  "2026-02-25",
                          "form":  "10-K",
                          "tag":  "CommonStockDividendsPerShareDeclared",
                          "unit":  "USD/shares",
                          "val":  0.04
                      }
                  ],
    "dps_series":  [
                       {
                           "end":  "2011-01-30",
                           "val":  0
                       },
                       {
                           "end":  "2012-01-29",
                           "val":  0
                       },
                       {
                           "end":  "2013-01-27",
                           "val":  0.075
                       },
                       {
                           "end":  "2014-01-26",
                           "val":  0.31
                       },
                       {
                           "end":  "2015-01-25",
                           "val":  0.34
                       },
                       {
                           "end":  "2016-01-31",
                           "val":  0.115
                       },
                       {
                           "end":  "2017-01-29",
                           "val":  0.485
                       },
                       {
                           "end":  "2018-01-28",
                           "val":  0.57
                       },
                       {
                           "end":  "2019-01-27",
                           "val":  0.61
                       },
                       {
                           "end":  "2020-01-26",
                           "val":  0.16
                       },
                       {
                           "end":  "2021-01-31",
                           "val":  0.16
                       },
                       {
                           "end":  "2022-01-30",
                           "val":  0.16
                       },
                       {
                           "end":  "2023-01-29",
                           "val":  0.016
                       },
                       {
                           "end":  "2024-01-28",
                           "val":  0.016
                       },
                       {
                           "end":  "2025-01-26",
                           "val":  0.034
                       },
                       {
                           "end":  "2026-01-25",
                           "val":  0.04
                       }
                   ],
    "gross_profit":  [
                         {
                             "end":  "2008-01-27",
                             "val":  1869280000
                         },
                         {
                             "end":  "2009-01-25",
                             "val":  1174269000
                         },
                         {
                             "end":  "2010-01-31",
                             "val":  1176923000
                         },
                         {
                             "end":  "2011-01-30",
                             "val":  1409090000
                         },
                         {
                             "end":  "2012-01-29",
                             "val":  2056517000
                         },
                         {
                             "end":  "2013-01-27",
                             "val":  2226343000
                         },
                         {
                             "end":  "2014-01-26",
                             "val":  2268000000
                         },
                         {
                             "end":  "2015-01-25",
                             "val":  2599000000
                         },
                         {
                             "end":  "2016-01-31",
                             "val":  2811000000
                         },
                         {
                             "end":  "2017-01-29",
                             "val":  4063000000
                         },
                         {
                             "end":  "2018-01-28",
                             "val":  5822000000
                         },
                         {
                             "end":  "2019-01-27",
                             "val":  7171000000
                         },
                         {
                             "end":  "2020-01-26",
                             "val":  6768000000
                         },
                         {
                             "end":  "2021-01-31",
                             "val":  10396000000
                         },
                         {
                             "end":  "2022-01-30",
                             "val":  17475000000
                         },
                         {
                             "end":  "2023-01-29",
                             "val":  15356000000
                         },
                         {
                             "end":  "2024-01-28",
                             "val":  44301000000
                         },
                         {
                             "end":  "2025-01-26",
                             "val":  97858000000
                         },
                         {
                             "end":  "2026-01-25",
                             "val":  153463000000
                         }
                     ],
    "gross_profit_audit":  [
                               {
                                   "accn":  "0001045810-10-000006",
                                   "end":  "2008-01-27",
                                   "filed":  "2010-03-18",
                                   "form":  "10-K",
                                   "tag":  "GrossProfit",
                                   "unit":  "USD",
                                   "val":  1869280000
                               },
                               {
                                   "accn":  "0001045810-11-000015",
                                   "end":  "2009-01-25",
                                   "filed":  "2011-03-16",
                                   "form":  "10-K",
                                   "tag":  "GrossProfit",
                                   "unit":  "USD",
                                   "val":  1174269000
                               },
                               {
                                   "accn":  "0001045810-12-000013",
                                   "end":  "2010-01-31",
                                   "filed":  "2012-03-13",
                                   "form":  "10-K",
                                   "tag":  "GrossProfit",
                                   "unit":  "USD",
                                   "val":  1176923000
                               },
                               {
                                   "accn":  "0001045810-13-000008",
                                   "end":  "2011-01-30",
                                   "filed":  "2013-03-12",
                                   "form":  "10-K",
                                   "tag":  "GrossProfit",
                                   "unit":  "USD",
                                   "val":  1409090000
                               },
                               {
                                   "accn":  "0001045810-14-000030",
                                   "end":  "2012-01-29",
                                   "filed":  "2014-03-13",
                                   "form":  "10-K",
                                   "tag":  "GrossProfit",
                                   "unit":  "USD",
                                   "val":  2056517000
                               },
                               {
                                   "accn":  "0001045810-15-000036",
                                   "end":  "2013-01-27",
                                   "filed":  "2015-03-12",
                                   "form":  "10-K",
                                   "tag":  "GrossProfit",
                                   "unit":  "USD",
                                   "val":  2226343000
                               },
                               {
                                   "accn":  "0001045810-16-000205",
                                   "end":  "2014-01-26",
                                   "filed":  "2016-03-17",
                                   "form":  "10-K",
                                   "tag":  "GrossProfit",
                                   "unit":  "USD",
                                   "val":  2268000000
                               },
                               {
                                   "accn":  "0001045810-17-000027",
                                   "end":  "2015-01-25",
                                   "filed":  "2017-03-01",
                                   "form":  "10-K",
                                   "tag":  "GrossProfit",
                                   "unit":  "USD",
                                   "val":  2599000000
                               },
                               {
                                   "accn":  "0001045810-18-000010",
                                   "end":  "2016-01-31",
                                   "filed":  "2018-02-28",
                                   "form":  "10-K",
                                   "tag":  "GrossProfit",
                                   "unit":  "USD",
                                   "val":  2811000000
                               },
                               {
                                   "accn":  "0001045810-19-000023",
                                   "end":  "2017-01-29",
                                   "filed":  "2019-02-21",
                                   "form":  "10-K",
                                   "tag":  "GrossProfit",
                                   "unit":  "USD",
                                   "val":  4063000000
                               },
                               {
                                   "accn":  "0001045810-20-000010",
                                   "end":  "2018-01-28",
                                   "filed":  "2020-02-20",
                                   "form":  "10-K",
                                   "tag":  "GrossProfit",
                                   "unit":  "USD",
                                   "val":  5822000000
                               },
                               {
                                   "accn":  "0001045810-21-000010",
                                   "end":  "2019-01-27",
                                   "filed":  "2021-02-26",
                                   "form":  "10-K",
                                   "tag":  "GrossProfit",
                                   "unit":  "USD",
                                   "val":  7171000000
                               },
                               {
                                   "accn":  "0001045810-22-000036",
                                   "end":  "2020-01-26",
                                   "filed":  "2022-03-18",
                                   "form":  "10-K",
                                   "tag":  "GrossProfit",
                                   "unit":  "USD",
                                   "val":  6768000000
                               },
                               {
                                   "accn":  "0001045810-23-000017",
                                   "end":  "2021-01-31",
                                   "filed":  "2023-02-24",
                                   "form":  "10-K",
                                   "tag":  "GrossProfit",
                                   "unit":  "USD",
                                   "val":  10396000000
                               },
                               {
                                   "accn":  "0001045810-24-000029",
                                   "end":  "2022-01-30",
                                   "filed":  "2024-02-21",
                                   "form":  "10-K",
                                   "tag":  "GrossProfit",
                                   "unit":  "USD",
                                   "val":  17475000000
                               },
                               {
                                   "accn":  "0001045810-25-000023",
                                   "end":  "2023-01-29",
                                   "filed":  "2025-02-26",
                                   "form":  "10-K",
                                   "tag":  "GrossProfit",
                                   "unit":  "USD",
                                   "val":  15356000000
                               },
                               {
                                   "accn":  "0001045810-26-000021",
                                   "end":  "2024-01-28",
                                   "filed":  "2026-02-25",
                                   "form":  "10-K",
                                   "tag":  "GrossProfit",
                                   "unit":  "USD",
                                   "val":  44301000000
                               },
                               {
                                   "accn":  "0001045810-26-000021",
                                   "end":  "2025-01-26",
                                   "filed":  "2026-02-25",
                                   "form":  "10-K",
                                   "tag":  "GrossProfit",
                                   "unit":  "USD",
                                   "val":  97858000000
                               },
                               {
                                   "accn":  "0001045810-26-000021",
                                   "end":  "2026-01-25",
                                   "filed":  "2026-02-25",
                                   "form":  "10-K",
                                   "tag":  "GrossProfit",
                                   "unit":  "USD",
                                   "val":  153463000000
                               }
                           ],
    "long_term_debt":  8470000000,
    "long_term_debt_audit":  {
                                 "accn":  "0001045810-26-000052",
                                 "end":  "2026-04-26",
                                 "filed":  "2026-05-20",
                                 "val":  8470000000
                             },
    "net_income":  [
                       {
                           "end":  "2008-01-27",
                           "val":  797645000
                       },
                       {
                           "end":  "2009-01-25",
                           "val":  -30041000
                       },
                       {
                           "end":  "2010-01-31",
                           "val":  -67987000
                       },
                       {
                           "end":  "2011-01-30",
                           "val":  253146000
                       },
                       {
                           "end":  "2012-01-29",
                           "val":  581090000
                       },
                       {
                           "end":  "2013-01-27",
                           "val":  562536000
                       },
                       {
                           "end":  "2014-01-26",
                           "val":  440000000
                       },
                       {
                           "end":  "2015-01-25",
                           "val":  631000000
                       },
                       {
                           "end":  "2016-01-31",
                           "val":  614000000
                       },
                       {
                           "end":  "2017-01-29",
                           "val":  1666000000
                       },
                       {
                           "end":  "2018-01-28",
                           "val":  3047000000
                       },
                       {
                           "end":  "2019-01-27",
                           "val":  4141000000
                       },
                       {
                           "end":  "2020-01-26",
                           "val":  2796000000
                       },
                       {
                           "end":  "2021-01-31",
                           "val":  4332000000
                       },
                       {
                           "end":  "2022-01-30",
                           "val":  9752000000
                       },
                       {
                           "end":  "2023-01-29",
                           "val":  4368000000
                       },
                       {
                           "end":  "2024-01-28",
                           "val":  29760000000
                       },
                       {
                           "end":  "2025-01-26",
                           "val":  72880000000
                       },
                       {
                           "end":  "2026-01-25",
                           "val":  120067000000
                       }
                   ],
    "net_income_audit":  [
                             {
                                 "accn":  "0001045810-10-000006",
                                 "end":  "2008-01-27",
                                 "filed":  "2010-03-18",
                                 "form":  "10-K",
                                 "tag":  "NetIncomeLoss",
                                 "unit":  "USD",
                                 "val":  797645000
                             },
                             {
                                 "accn":  "0001045810-11-000015",
                                 "end":  "2009-01-25",
                                 "filed":  "2011-03-16",
                                 "form":  "10-K",
                                 "tag":  "NetIncomeLoss",
                                 "unit":  "USD",
                                 "val":  -30041000
                             },
                             {
                                 "accn":  "0001045810-12-000013",
                                 "end":  "2010-01-31",
                                 "filed":  "2012-03-13",
                                 "form":  "10-K",
                                 "tag":  "NetIncomeLoss",
                                 "unit":  "USD",
                                 "val":  -67987000
                             },
                             {
                                 "accn":  "0001045810-13-000008",
                                 "end":  "2011-01-30",
                                 "filed":  "2013-03-12",
                                 "form":  "10-K",
                                 "tag":  "NetIncomeLoss",
                                 "unit":  "USD",
                                 "val":  253146000
                             },
                             {
                                 "accn":  "0001045810-14-000030",
                                 "end":  "2012-01-29",
                                 "filed":  "2014-03-13",
                                 "form":  "10-K",
                                 "tag":  "NetIncomeLoss",
                                 "unit":  "USD",
                                 "val":  581090000
                             },
                             {
                                 "accn":  "0001045810-15-000036",
                                 "end":  "2013-01-27",
                                 "filed":  "2015-03-12",
                                 "form":  "10-K",
                                 "tag":  "NetIncomeLoss",
                                 "unit":  "USD",
                                 "val":  562536000
                             },
                             {
                                 "accn":  "0001045810-16-000205",
                                 "end":  "2014-01-26",
                                 "filed":  "2016-03-17",
                                 "form":  "10-K",
                                 "tag":  "NetIncomeLoss",
                                 "unit":  "USD",
                                 "val":  440000000
                             },
                             {
                                 "accn":  "0001045810-17-000027",
                                 "end":  "2015-01-25",
                                 "filed":  "2017-03-01",
                                 "form":  "10-K",
                                 "tag":  "NetIncomeLoss",
                                 "unit":  "USD",
                                 "val":  631000000
                             },
                             {
                                 "accn":  "0001045810-18-000010",
                                 "end":  "2016-01-31",
                                 "filed":  "2018-02-28",
                                 "form":  "10-K",
                                 "tag":  "NetIncomeLoss",
                                 "unit":  "USD",
                                 "val":  614000000
                             },
                             {
                                 "accn":  "0001045810-19-000023",
                                 "end":  "2017-01-29",
                                 "filed":  "2019-02-21",
                                 "form":  "10-K",
                                 "tag":  "NetIncomeLoss",
                                 "unit":  "USD",
                                 "val":  1666000000
                             },
                             {
                                 "accn":  "0001045810-20-000010",
                                 "end":  "2018-01-28",
                                 "filed":  "2020-02-20",
                                 "form":  "10-K",
                                 "tag":  "NetIncomeLoss",
                                 "unit":  "USD",
                                 "val":  3047000000
                             },
                             {
                                 "accn":  "0001045810-21-000010",
                                 "end":  "2019-01-27",
                                 "filed":  "2021-02-26",
                                 "form":  "10-K",
                                 "tag":  "NetIncomeLoss",
                                 "unit":  "USD",
                                 "val":  4141000000
                             },
                             {
                                 "accn":  "0001045810-22-000036",
                                 "end":  "2020-01-26",
                                 "filed":  "2022-03-18",
                                 "form":  "10-K",
                                 "tag":  "NetIncomeLoss",
                                 "unit":  "USD",
                                 "val":  2796000000
                             },
                             {
                                 "accn":  "0001045810-23-000017",
                                 "end":  "2021-01-31",
                                 "filed":  "2023-02-24",
                                 "form":  "10-K",
                                 "tag":  "NetIncomeLoss",
                                 "unit":  "USD",
                                 "val":  4332000000
                             },
                             {
                                 "accn":  "0001045810-24-000029",
                                 "end":  "2022-01-30",
                                 "filed":  "2024-02-21",
                                 "form":  "10-K",
                                 "tag":  "NetIncomeLoss",
                                 "unit":  "USD",
                                 "val":  9752000000
                             },
                             {
                                 "accn":  "0001045810-25-000023",
                                 "end":  "2023-01-29",
                                 "filed":  "2025-02-26",
                                 "form":  "10-K",
                                 "tag":  "NetIncomeLoss",
                                 "unit":  "USD",
                                 "val":  4368000000
                             },
                             {
                                 "accn":  "0001045810-26-000021",
                                 "end":  "2024-01-28",
                                 "filed":  "2026-02-25",
                                 "form":  "10-K",
                                 "tag":  "NetIncomeLoss",
                                 "unit":  "USD",
                                 "val":  29760000000
                             },
                             {
                                 "accn":  "0001045810-26-000021",
                                 "end":  "2025-01-26",
                                 "filed":  "2026-02-25",
                                 "form":  "10-K",
                                 "tag":  "NetIncomeLoss",
                                 "unit":  "USD",
                                 "val":  72880000000
                             },
                             {
                                 "accn":  "0001045810-26-000021",
                                 "end":  "2026-01-25",
                                 "filed":  "2026-02-25",
                                 "form":  "10-K",
                                 "tag":  "NetIncomeLoss",
                                 "unit":  "USD",
                                 "val":  120067000000
                             }
                         ],
    "ocf":  [
                {
                    "end":  "2008-01-27",
                    "val":  1270196000
                },
                {
                    "end":  "2009-01-25",
                    "val":  249360000
                },
                {
                    "end":  "2010-01-31",
                    "val":  487807000
                },
                {
                    "end":  "2011-01-30",
                    "val":  675797000
                },
                {
                    "end":  "2012-01-29",
                    "val":  909156000
                },
                {
                    "end":  "2013-01-27",
                    "val":  824172000
                },
                {
                    "end":  "2014-01-26",
                    "val":  835000000
                },
                {
                    "end":  "2015-01-25",
                    "val":  906000000
                },
                {
                    "end":  "2016-01-31",
                    "val":  1175000000
                },
                {
                    "end":  "2017-01-29",
                    "val":  1672000000
                },
                {
                    "end":  "2018-01-28",
                    "val":  3502000000
                },
                {
                    "end":  "2019-01-27",
                    "val":  3743000000
                },
                {
                    "end":  "2020-01-26",
                    "val":  4761000000
                },
                {
                    "end":  "2021-01-31",
                    "val":  5822000000
                },
                {
                    "end":  "2022-01-30",
                    "val":  9108000000
                },
                {
                    "end":  "2023-01-29",
                    "val":  5641000000
                },
                {
                    "end":  "2024-01-28",
                    "val":  28090000000
                },
                {
                    "end":  "2025-01-26",
                    "val":  64089000000
                },
                {
                    "end":  "2026-01-25",
                    "val":  102718000000
                }
            ],
    "ocf_audit":  [
                      {
                          "accn":  "0001045810-10-000006",
                          "end":  "2008-01-27",
                          "filed":  "2010-03-18",
                          "form":  "10-K",
                          "tag":  "NetCashProvidedByUsedInOperatingActivities",
                          "unit":  "USD",
                          "val":  1270196000
                      },
                      {
                          "accn":  "0001045810-11-000015",
                          "end":  "2009-01-25",
                          "filed":  "2011-03-16",
                          "form":  "10-K",
                          "tag":  "NetCashProvidedByUsedInOperatingActivities",
                          "unit":  "USD",
                          "val":  249360000
                      },
                      {
                          "accn":  "0001045810-12-000013",
                          "end":  "2010-01-31",
                          "filed":  "2012-03-13",
                          "form":  "10-K",
                          "tag":  "NetCashProvidedByUsedInOperatingActivities",
                          "unit":  "USD",
                          "val":  487807000
                      },
                      {
                          "accn":  "0001045810-13-000008",
                          "end":  "2011-01-30",
                          "filed":  "2013-03-12",
                          "form":  "10-K",
                          "tag":  "NetCashProvidedByUsedInOperatingActivities",
                          "unit":  "USD",
                          "val":  675797000
                      },
                      {
                          "accn":  "0001045810-14-000030",
                          "end":  "2012-01-29",
                          "filed":  "2014-03-13",
                          "form":  "10-K",
                          "tag":  "NetCashProvidedByUsedInOperatingActivities",
                          "unit":  "USD",
                          "val":  909156000
                      },
                      {
                          "accn":  "0001045810-15-000036",
                          "end":  "2013-01-27",
                          "filed":  "2015-03-12",
                          "form":  "10-K",
                          "tag":  "NetCashProvidedByUsedInOperatingActivities",
                          "unit":  "USD",
                          "val":  824172000
                      },
                      {
                          "accn":  "0001045810-16-000205",
                          "end":  "2014-01-26",
                          "filed":  "2016-03-17",
                          "form":  "10-K",
                          "tag":  "NetCashProvidedByUsedInOperatingActivities",
                          "unit":  "USD",
                          "val":  835000000
                      },
                      {
                          "accn":  "0001045810-17-000027",
                          "end":  "2015-01-25",
                          "filed":  "2017-03-01",
                          "form":  "10-K",
                          "tag":  "NetCashProvidedByUsedInOperatingActivities",
                          "unit":  "USD",
                          "val":  906000000
                      },
                      {
                          "accn":  "0001045810-18-000010",
                          "end":  "2016-01-31",
                          "filed":  "2018-02-28",
                          "form":  "10-K",
                          "tag":  "NetCashProvidedByUsedInOperatingActivities",
                          "unit":  "USD",
                          "val":  1175000000
                      },
                      {
                          "accn":  "0001045810-19-000023",
                          "end":  "2017-01-29",
                          "filed":  "2019-02-21",
                          "form":  "10-K",
                          "tag":  "NetCashProvidedByUsedInOperatingActivities",
                          "unit":  "USD",
                          "val":  1672000000
                      },
                      {
                          "accn":  "0001045810-20-000010",
                          "end":  "2018-01-28",
                          "filed":  "2020-02-20",
                          "form":  "10-K",
                          "tag":  "NetCashProvidedByUsedInOperatingActivities",
                          "unit":  "USD",
                          "val":  3502000000
                      },
                      {
                          "accn":  "0001045810-21-000010",
                          "end":  "2019-01-27",
                          "filed":  "2021-02-26",
                          "form":  "10-K",
                          "tag":  "NetCashProvidedByUsedInOperatingActivities",
                          "unit":  "USD",
                          "val":  3743000000
                      },
                      {
                          "accn":  "0001045810-22-000036",
                          "end":  "2020-01-26",
                          "filed":  "2022-03-18",
                          "form":  "10-K",
                          "tag":  "NetCashProvidedByUsedInOperatingActivities",
                          "unit":  "USD",
                          "val":  4761000000
                      },
                      {
                          "accn":  "0001045810-23-000017",
                          "end":  "2021-01-31",
                          "filed":  "2023-02-24",
                          "form":  "10-K",
                          "tag":  "NetCashProvidedByUsedInOperatingActivities",
                          "unit":  "USD",
                          "val":  5822000000
                      },
                      {
                          "accn":  "0001045810-24-000029",
                          "end":  "2022-01-30",
                          "filed":  "2024-02-21",
                          "form":  "10-K",
                          "tag":  "NetCashProvidedByUsedInOperatingActivities",
                          "unit":  "USD",
                          "val":  9108000000
                      },
                      {
                          "accn":  "0001045810-25-000023",
                          "end":  "2023-01-29",
                          "filed":  "2025-02-26",
                          "form":  "10-K",
                          "tag":  "NetCashProvidedByUsedInOperatingActivities",
                          "unit":  "USD",
                          "val":  5641000000
                      },
                      {
                          "accn":  "0001045810-26-000021",
                          "end":  "2024-01-28",
                          "filed":  "2026-02-25",
                          "form":  "10-K",
                          "tag":  "NetCashProvidedByUsedInOperatingActivities",
                          "unit":  "USD",
                          "val":  28090000000
                      },
                      {
                          "accn":  "0001045810-26-000021",
                          "end":  "2025-01-26",
                          "filed":  "2026-02-25",
                          "form":  "10-K",
                          "tag":  "NetCashProvidedByUsedInOperatingActivities",
                          "unit":  "USD",
                          "val":  64089000000
                      },
                      {
                          "accn":  "0001045810-26-000021",
                          "end":  "2026-01-25",
                          "filed":  "2026-02-25",
                          "form":  "10-K",
                          "tag":  "NetCashProvidedByUsedInOperatingActivities",
                          "unit":  "USD",
                          "val":  102718000000
                      }
                  ],
    "operating_income":  [
                             {
                                 "end":  "2008-01-27",
                                 "val":  836346000
                             },
                             {
                                 "end":  "2009-01-25",
                                 "val":  -70700000
                             },
                             {
                                 "end":  "2010-01-31",
                                 "val":  -98945000
                             },
                             {
                                 "end":  "2011-01-30",
                                 "val":  255747000
                             },
                             {
                                 "end":  "2012-01-29",
                                 "val":  648299000
                             },
                             {
                                 "end":  "2013-01-27",
                                 "val":  648239000
                             },
                             {
                                 "end":  "2014-01-26",
                                 "val":  496000000
                             },
                             {
                                 "end":  "2015-01-25",
                                 "val":  759000000
                             },
                             {
                                 "end":  "2016-01-31",
                                 "val":  747000000
                             },
                             {
                                 "end":  "2017-01-29",
                                 "val":  1934000000
                             },
                             {
                                 "end":  "2018-01-28",
                                 "val":  3210000000
                             },
                             {
                                 "end":  "2019-01-27",
                                 "val":  3804000000
                             },
                             {
                                 "end":  "2020-01-26",
                                 "val":  2846000000
                             },
                             {
                                 "end":  "2021-01-31",
                                 "val":  4532000000
                             },
                             {
                                 "end":  "2022-01-30",
                                 "val":  10041000000
                             },
                             {
                                 "end":  "2023-01-29",
                                 "val":  4224000000
                             },
                             {
                                 "end":  "2024-01-28",
                                 "val":  32972000000
                             },
                             {
                                 "end":  "2025-01-26",
                                 "val":  81453000000
                             },
                             {
                                 "end":  "2026-01-25",
                                 "val":  130387000000
                             }
                         ],
    "operating_income_audit":  [
                                   {
                                       "accn":  "0001045810-10-000006",
                                       "end":  "2008-01-27",
                                       "filed":  "2010-03-18",
                                       "form":  "10-K",
                                       "tag":  "OperatingIncomeLoss",
                                       "unit":  "USD",
                                       "val":  836346000
                                   },
                                   {
                                       "accn":  "0001045810-11-000015",
                                       "end":  "2009-01-25",
                                       "filed":  "2011-03-16",
                                       "form":  "10-K",
                                       "tag":  "OperatingIncomeLoss",
                                       "unit":  "USD",
                                       "val":  -70700000
                                   },
                                   {
                                       "accn":  "0001045810-12-000013",
                                       "end":  "2010-01-31",
                                       "filed":  "2012-03-13",
                                       "form":  "10-K",
                                       "tag":  "OperatingIncomeLoss",
                                       "unit":  "USD",
                                       "val":  -98945000
                                   },
                                   {
                                       "accn":  "0001045810-13-000008",
                                       "end":  "2011-01-30",
                                       "filed":  "2013-03-12",
                                       "form":  "10-K",
                                       "tag":  "OperatingIncomeLoss",
                                       "unit":  "USD",
                                       "val":  255747000
                                   },
                                   {
                                       "accn":  "0001045810-14-000030",
                                       "end":  "2012-01-29",
                                       "filed":  "2014-03-13",
                                       "form":  "10-K",
                                       "tag":  "OperatingIncomeLoss",
                                       "unit":  "USD",
                                       "val":  648299000
                                   },
                                   {
                                       "accn":  "0001045810-15-000036",
                                       "end":  "2013-01-27",
                                       "filed":  "2015-03-12",
                                       "form":  "10-K",
                                       "tag":  "OperatingIncomeLoss",
                                       "unit":  "USD",
                                       "val":  648239000
                                   },
                                   {
                                       "accn":  "0001045810-16-000205",
                                       "end":  "2014-01-26",
                                       "filed":  "2016-03-17",
                                       "form":  "10-K",
                                       "tag":  "OperatingIncomeLoss",
                                       "unit":  "USD",
                                       "val":  496000000
                                   },
                                   {
                                       "accn":  "0001045810-17-000027",
                                       "end":  "2015-01-25",
                                       "filed":  "2017-03-01",
                                       "form":  "10-K",
                                       "tag":  "OperatingIncomeLoss",
                                       "unit":  "USD",
                                       "val":  759000000
                                   },
                                   {
                                       "accn":  "0001045810-18-000010",
                                       "end":  "2016-01-31",
                                       "filed":  "2018-02-28",
                                       "form":  "10-K",
                                       "tag":  "OperatingIncomeLoss",
                                       "unit":  "USD",
                                       "val":  747000000
                                   },
                                   {
                                       "accn":  "0001045810-19-000023",
                                       "end":  "2017-01-29",
                                       "filed":  "2019-02-21",
                                       "form":  "10-K",
                                       "tag":  "OperatingIncomeLoss",
                                       "unit":  "USD",
                                       "val":  1934000000
                                   },
                                   {
                                       "accn":  "0001045810-20-000010",
                                       "end":  "2018-01-28",
                                       "filed":  "2020-02-20",
                                       "form":  "10-K",
                                       "tag":  "OperatingIncomeLoss",
                                       "unit":  "USD",
                                       "val":  3210000000
                                   },
                                   {
                                       "accn":  "0001045810-21-000010",
                                       "end":  "2019-01-27",
                                       "filed":  "2021-02-26",
                                       "form":  "10-K",
                                       "tag":  "OperatingIncomeLoss",
                                       "unit":  "USD",
                                       "val":  3804000000
                                   },
                                   {
                                       "accn":  "0001045810-22-000036",
                                       "end":  "2020-01-26",
                                       "filed":  "2022-03-18",
                                       "form":  "10-K",
                                       "tag":  "OperatingIncomeLoss",
                                       "unit":  "USD",
                                       "val":  2846000000
                                   },
                                   {
                                       "accn":  "0001045810-23-000017",
                                       "end":  "2021-01-31",
                                       "filed":  "2023-02-24",
                                       "form":  "10-K",
                                       "tag":  "OperatingIncomeLoss",
                                       "unit":  "USD",
                                       "val":  4532000000
                                   },
                                   {
                                       "accn":  "0001045810-24-000029",
                                       "end":  "2022-01-30",
                                       "filed":  "2024-02-21",
                                       "form":  "10-K",
                                       "tag":  "OperatingIncomeLoss",
                                       "unit":  "USD",
                                       "val":  10041000000
                                   },
                                   {
                                       "accn":  "0001045810-25-000023",
                                       "end":  "2023-01-29",
                                       "filed":  "2025-02-26",
                                       "form":  "10-K",
                                       "tag":  "OperatingIncomeLoss",
                                       "unit":  "USD",
                                       "val":  4224000000
                                   },
                                   {
                                       "accn":  "0001045810-26-000021",
                                       "end":  "2024-01-28",
                                       "filed":  "2026-02-25",
                                       "form":  "10-K",
                                       "tag":  "OperatingIncomeLoss",
                                       "unit":  "USD",
                                       "val":  32972000000
                                   },
                                   {
                                       "accn":  "0001045810-26-000021",
                                       "end":  "2025-01-26",
                                       "filed":  "2026-02-25",
                                       "form":  "10-K",
                                       "tag":  "OperatingIncomeLoss",
                                       "unit":  "USD",
                                       "val":  81453000000
                                   },
                                   {
                                       "accn":  "0001045810-26-000021",
                                       "end":  "2026-01-25",
                                       "filed":  "2026-02-25",
                                       "form":  "10-K",
                                       "tag":  "OperatingIncomeLoss",
                                       "unit":  "USD",
                                       "val":  130387000000
                                   }
                               ],
    "restricted_cash":  null,
    "revenue":  [
                    {
                        "end":  "2008-01-27",
                        "val":  4097860000
                    },
                    {
                        "end":  "2009-01-25",
                        "val":  3424859000
                    },
                    {
                        "end":  "2010-01-31",
                        "val":  3326445000
                    },
                    {
                        "end":  "2011-01-30",
                        "val":  3543309000
                    },
                    {
                        "end":  "2012-01-29",
                        "val":  3997930000
                    },
                    {
                        "end":  "2013-01-27",
                        "val":  4280159000
                    },
                    {
                        "end":  "2014-01-26",
                        "val":  4130000000
                    },
                    {
                        "end":  "2015-01-25",
                        "val":  4682000000
                    },
                    {
                        "end":  "2016-01-31",
                        "val":  5010000000
                    },
                    {
                        "end":  "2017-01-29",
                        "val":  6910000000
                    },
                    {
                        "end":  "2018-01-28",
                        "val":  9714000000
                    },
                    {
                        "end":  "2020-01-26",
                        "val":  10918000000
                    },
                    {
                        "end":  "2021-01-31",
                        "val":  16675000000
                    },
                    {
                        "end":  "2022-01-30",
                        "val":  26914000000
                    },
                    {
                        "end":  "2023-01-29",
                        "val":  26974000000
                    },
                    {
                        "end":  "2024-01-28",
                        "val":  60922000000
                    },
                    {
                        "end":  "2025-01-26",
                        "val":  130497000000
                    },
                    {
                        "end":  "2026-01-25",
                        "val":  215938000000
                    }
                ],
    "revenue_audit":  [
                          {
                              "accn":  "0001045810-10-000006",
                              "end":  "2008-01-27",
                              "filed":  "2010-03-18",
                              "form":  "10-K",
                              "tag":  "Revenues",
                              "unit":  "USD",
                              "val":  4097860000
                          },
                          {
                              "accn":  "0001045810-11-000015",
                              "end":  "2009-01-25",
                              "filed":  "2011-03-16",
                              "form":  "10-K",
                              "tag":  "Revenues",
                              "unit":  "USD",
                              "val":  3424859000
                          },
                          {
                              "accn":  "0001045810-12-000013",
                              "end":  "2010-01-31",
                              "filed":  "2012-03-13",
                              "form":  "10-K",
                              "tag":  "Revenues",
                              "unit":  "USD",
                              "val":  3326445000
                          },
                          {
                              "accn":  "0001045810-13-000008",
                              "end":  "2011-01-30",
                              "filed":  "2013-03-12",
                              "form":  "10-K",
                              "tag":  "Revenues",
                              "unit":  "USD",
                              "val":  3543309000
                          },
                          {
                              "accn":  "0001045810-14-000030",
                              "end":  "2012-01-29",
                              "filed":  "2014-03-13",
                              "form":  "10-K",
                              "tag":  "Revenues",
                              "unit":  "USD",
                              "val":  3997930000
                          },
                          {
                              "accn":  "0001045810-15-000036",
                              "end":  "2013-01-27",
                              "filed":  "2015-03-12",
                              "form":  "10-K",
                              "tag":  "Revenues",
                              "unit":  "USD",
                              "val":  4280159000
                          },
                          {
                              "accn":  "0001045810-16-000205",
                              "end":  "2014-01-26",
                              "filed":  "2016-03-17",
                              "form":  "10-K",
                              "tag":  "Revenues",
                              "unit":  "USD",
                              "val":  4130000000
                          },
                          {
                              "accn":  "0001045810-17-000027",
                              "end":  "2015-01-25",
                              "filed":  "2017-03-01",
                              "form":  "10-K",
                              "tag":  "Revenues",
                              "unit":  "USD",
                              "val":  4682000000
                          },
                          {
                              "accn":  "0001045810-18-000010",
                              "end":  "2016-01-31",
                              "filed":  "2018-02-28",
                              "form":  "10-K",
                              "tag":  "Revenues",
                              "unit":  "USD",
                              "val":  5010000000
                          },
                          {
                              "accn":  "0001045810-18-000010",
                              "end":  "2017-01-29",
                              "filed":  "2018-02-28",
                              "form":  "10-K",
                              "tag":  "Revenues",
                              "unit":  "USD",
                              "val":  6910000000
                          },
                          {
                              "accn":  "0001045810-18-000010",
                              "end":  "2018-01-28",
                              "filed":  "2018-02-28",
                              "form":  "10-K",
                              "tag":  "Revenues",
                              "unit":  "USD",
                              "val":  9714000000
                          },
                          {
                              "accn":  "0001045810-22-000036",
                              "end":  "2020-01-26",
                              "filed":  "2022-03-18",
                              "form":  "10-K",
                              "tag":  "Revenues",
                              "unit":  "USD",
                              "val":  10918000000
                          },
                          {
                              "accn":  "0001045810-23-000017",
                              "end":  "2021-01-31",
                              "filed":  "2023-02-24",
                              "form":  "10-K",
                              "tag":  "Revenues",
                              "unit":  "USD",
                              "val":  16675000000
                          },
                          {
                              "accn":  "0001045810-24-000029",
                              "end":  "2022-01-30",
                              "filed":  "2024-02-21",
                              "form":  "10-K",
                              "tag":  "Revenues",
                              "unit":  "USD",
                              "val":  26914000000
                          },
                          {
                              "accn":  "0001045810-25-000023",
                              "end":  "2023-01-29",
                              "filed":  "2025-02-26",
                              "form":  "10-K",
                              "tag":  "Revenues",
                              "unit":  "USD",
                              "val":  26974000000
                          },
                          {
                              "accn":  "0001045810-26-000021",
                              "end":  "2024-01-28",
                              "filed":  "2026-02-25",
                              "form":  "10-K",
                              "tag":  "Revenues",
                              "unit":  "USD",
                              "val":  60922000000
                          },
                          {
                              "accn":  "0001045810-26-000021",
                              "end":  "2025-01-26",
                              "filed":  "2026-02-25",
                              "form":  "10-K",
                              "tag":  "Revenues",
                              "unit":  "USD",
                              "val":  130497000000
                          },
                          {
                              "accn":  "0001045810-26-000021",
                              "end":  "2026-01-25",
                              "filed":  "2026-02-25",
                              "form":  "10-K",
                              "tag":  "Revenues",
                              "unit":  "USD",
                              "val":  215938000000
                          }
                      ],
    "rpo":  2600000000,
    "rpo_audit":  {
                      "accn":  "0001045810-26-000052",
                      "end":  "2026-04-26",
                      "filed":  "2026-05-20",
                      "val":  2600000000
                  },
    "sbc":  [
                {
                    "end":  "2008-01-27",
                    "val":  133365000
                },
                {
                    "end":  "2009-01-25",
                    "val":  162706000
                },
                {
                    "end":  "2010-01-31",
                    "val":  107091000
                },
                {
                    "end":  "2011-01-30",
                    "val":  100353000
                },
                {
                    "end":  "2012-01-29",
                    "val":  136354000
                },
                {
                    "end":  "2013-01-27",
                    "val":  136662000
                },
                {
                    "end":  "2014-01-26",
                    "val":  136000000
                },
                {
                    "end":  "2015-01-25",
                    "val":  158000000
                },
                {
                    "end":  "2016-01-31",
                    "val":  204000000
                },
                {
                    "end":  "2017-01-29",
                    "val":  247000000
                },
                {
                    "end":  "2018-01-28",
                    "val":  391000000
                },
                {
                    "end":  "2019-01-27",
                    "val":  557000000
                },
                {
                    "end":  "2020-01-26",
                    "val":  844000000
                },
                {
                    "end":  "2021-01-31",
                    "val":  1397000000
                },
                {
                    "end":  "2022-01-30",
                    "val":  2004000000
                },
                {
                    "end":  "2023-01-29",
                    "val":  2709000000
                },
                {
                    "end":  "2024-01-28",
                    "val":  3549000000
                },
                {
                    "end":  "2025-01-26",
                    "val":  4737000000
                },
                {
                    "end":  "2026-01-25",
                    "val":  6386000000
                }
            ],
    "sbc_audit":  [
                      {
                          "accn":  "0001045810-10-000006",
                          "end":  "2008-01-27",
                          "filed":  "2010-03-18",
                          "form":  "10-K",
                          "tag":  "ShareBasedCompensation",
                          "unit":  "USD",
                          "val":  133365000
                      },
                      {
                          "accn":  "0001045810-11-000015",
                          "end":  "2009-01-25",
                          "filed":  "2011-03-16",
                          "form":  "10-K",
                          "tag":  "ShareBasedCompensation",
                          "unit":  "USD",
                          "val":  162706000
                      },
                      {
                          "accn":  "0001045810-12-000013",
                          "end":  "2010-01-31",
                          "filed":  "2012-03-13",
                          "form":  "10-K",
                          "tag":  "ShareBasedCompensation",
                          "unit":  "USD",
                          "val":  107091000
                      },
                      {
                          "accn":  "0001045810-13-000008",
                          "end":  "2011-01-30",
                          "filed":  "2013-03-12",
                          "form":  "10-K",
                          "tag":  "ShareBasedCompensation",
                          "unit":  "USD",
                          "val":  100353000
                      },
                      {
                          "accn":  "0001045810-14-000030",
                          "end":  "2012-01-29",
                          "filed":  "2014-03-13",
                          "form":  "10-K",
                          "tag":  "ShareBasedCompensation",
                          "unit":  "USD",
                          "val":  136354000
                      },
                      {
                          "accn":  "0001045810-15-000036",
                          "end":  "2013-01-27",
                          "filed":  "2015-03-12",
                          "form":  "10-K",
                          "tag":  "ShareBasedCompensation",
                          "unit":  "USD",
                          "val":  136662000
                      },
                      {
                          "accn":  "0001045810-16-000205",
                          "end":  "2014-01-26",
                          "filed":  "2016-03-17",
                          "form":  "10-K",
                          "tag":  "ShareBasedCompensation",
                          "unit":  "USD",
                          "val":  136000000
                      },
                      {
                          "accn":  "0001045810-17-000027",
                          "end":  "2015-01-25",
                          "filed":  "2017-03-01",
                          "form":  "10-K",
                          "tag":  "ShareBasedCompensation",
                          "unit":  "USD",
                          "val":  158000000
                      },
                      {
                          "accn":  "0001045810-18-000010",
                          "end":  "2016-01-31",
                          "filed":  "2018-02-28",
                          "form":  "10-K",
                          "tag":  "ShareBasedCompensation",
                          "unit":  "USD",
                          "val":  204000000
                      },
                      {
                          "accn":  "0001045810-19-000023",
                          "end":  "2017-01-29",
                          "filed":  "2019-02-21",
                          "form":  "10-K",
                          "tag":  "ShareBasedCompensation",
                          "unit":  "USD",
                          "val":  247000000
                      },
                      {
                          "accn":  "0001045810-20-000010",
                          "end":  "2018-01-28",
                          "filed":  "2020-02-20",
                          "form":  "10-K",
                          "tag":  "ShareBasedCompensation",
                          "unit":  "USD",
                          "val":  391000000
                      },
                      {
                          "accn":  "0001045810-21-000010",
                          "end":  "2019-01-27",
                          "filed":  "2021-02-26",
                          "form":  "10-K",
                          "tag":  "ShareBasedCompensation",
                          "unit":  "USD",
                          "val":  557000000
                      },
                      {
                          "accn":  "0001045810-22-000036",
                          "end":  "2020-01-26",
                          "filed":  "2022-03-18",
                          "form":  "10-K",
                          "tag":  "ShareBasedCompensation",
                          "unit":  "USD",
                          "val":  844000000
                      },
                      {
                          "accn":  "0001045810-23-000017",
                          "end":  "2021-01-31",
                          "filed":  "2023-02-24",
                          "form":  "10-K",
                          "tag":  "ShareBasedCompensation",
                          "unit":  "USD",
                          "val":  1397000000
                      },
                      {
                          "accn":  "0001045810-24-000029",
                          "end":  "2022-01-30",
                          "filed":  "2024-02-21",
                          "form":  "10-K",
                          "tag":  "ShareBasedCompensation",
                          "unit":  "USD",
                          "val":  2004000000
                      },
                      {
                          "accn":  "0001045810-25-000023",
                          "end":  "2023-01-29",
                          "filed":  "2025-02-26",
                          "form":  "10-K",
                          "tag":  "ShareBasedCompensation",
                          "unit":  "USD",
                          "val":  2709000000
                      },
                      {
                          "accn":  "0001045810-26-000021",
                          "end":  "2024-01-28",
                          "filed":  "2026-02-25",
                          "form":  "10-K",
                          "tag":  "ShareBasedCompensation",
                          "unit":  "USD",
                          "val":  3549000000
                      },
                      {
                          "accn":  "0001045810-26-000021",
                          "end":  "2025-01-26",
                          "filed":  "2026-02-25",
                          "form":  "10-K",
                          "tag":  "ShareBasedCompensation",
                          "unit":  "USD",
                          "val":  4737000000
                      },
                      {
                          "accn":  "0001045810-26-000021",
                          "end":  "2026-01-25",
                          "filed":  "2026-02-25",
                          "form":  "10-K",
                          "tag":  "ShareBasedCompensation",
                          "unit":  "USD",
                          "val":  6386000000
                      }
                  ],
    "shares_current":  24200000000,
    "shares_current_audit":  {
                                 "accn":  "0001045810-26-000052",
                                 "end":  "2026-05-15",
                                 "filed":  "2026-05-20",
                                 "val":  24200000000
                             },
    "shares_diluted":  [
                           {
                               "end":  "2008-01-27",
                               "val":  606732
                           },
                           {
                               "end":  "2009-01-25",
                               "val":  548126
                           },
                           {
                               "end":  "2010-01-31",
                               "val":  549574000
                           },
                           {
                               "end":  "2011-01-30",
                               "val":  588684000
                           },
                           {
                               "end":  "2012-01-29",
                               "val":  616371000
                           },
                           {
                               "end":  "2013-01-27",
                               "val":  624957000
                           },
                           {
                               "end":  "2014-01-26",
                               "val":  595000000
                           },
                           {
                               "end":  "2015-01-25",
                               "val":  563000000
                           },
                           {
                               "end":  "2016-01-31",
                               "val":  569000000
                           },
                           {
                               "end":  "2017-01-29",
                               "val":  649000000
                           },
                           {
                               "end":  "2018-01-28",
                               "val":  632000000
                           },
                           {
                               "end":  "2019-01-27",
                               "val":  625000000
                           },
                           {
                               "end":  "2020-01-26",
                               "val":  2472000000
                           },
                           {
                               "end":  "2021-01-31",
                               "val":  2510000000
                           },
                           {
                               "end":  "2022-01-30",
                               "val":  2535000000
                           },
                           {
                               "end":  "2023-01-29",
                               "val":  25070000000
                           },
                           {
                               "end":  "2024-01-28",
                               "val":  24940000000
                           },
                           {
                               "end":  "2025-01-26",
                               "val":  24804000000
                           },
                           {
                               "end":  "2026-01-25",
                               "val":  24514000000
                           }
                       ],
    "shares_diluted_audit":  [
                                 {
                                     "accn":  "0001045810-10-000006",
                                     "end":  "2008-01-27",
                                     "filed":  "2010-03-18",
                                     "form":  "10-K",
                                     "tag":  "WeightedAverageNumberOfDilutedSharesOutstanding",
                                     "unit":  "shares",
                                     "val":  606732
                                 },
                                 {
                                     "accn":  "0001045810-11-000015",
                                     "end":  "2009-01-25",
                                     "filed":  "2011-03-16",
                                     "form":  "10-K",
                                     "tag":  "WeightedAverageNumberOfDilutedSharesOutstanding",
                                     "unit":  "shares",
                                     "val":  548126
                                 },
                                 {
                                     "accn":  "0001045810-12-000013",
                                     "end":  "2010-01-31",
                                     "filed":  "2012-03-13",
                                     "form":  "10-K",
                                     "tag":  "WeightedAverageNumberOfDilutedSharesOutstanding",
                                     "unit":  "shares",
                                     "val":  549574000
                                 },
                                 {
                                     "accn":  "0001045810-13-000008",
                                     "end":  "2011-01-30",
                                     "filed":  "2013-03-12",
                                     "form":  "10-K",
                                     "tag":  "WeightedAverageNumberOfDilutedSharesOutstanding",
                                     "unit":  "shares",
                                     "val":  588684000
                                 },
                                 {
                                     "accn":  "0001045810-14-000030",
                                     "end":  "2012-01-29",
                                     "filed":  "2014-03-13",
                                     "form":  "10-K",
                                     "tag":  "WeightedAverageNumberOfDilutedSharesOutstanding",
                                     "unit":  "shares",
                                     "val":  616371000
                                 },
                                 {
                                     "accn":  "0001045810-15-000036",
                                     "end":  "2013-01-27",
                                     "filed":  "2015-03-12",
                                     "form":  "10-K",
                                     "tag":  "WeightedAverageNumberOfDilutedSharesOutstanding",
                                     "unit":  "shares",
                                     "val":  624957000
                                 },
                                 {
                                     "accn":  "0001045810-16-000205",
                                     "end":  "2014-01-26",
                                     "filed":  "2016-03-17",
                                     "form":  "10-K",
                                     "tag":  "WeightedAverageNumberOfDilutedSharesOutstanding",
                                     "unit":  "shares",
                                     "val":  595000000
                                 },
                                 {
                                     "accn":  "0001045810-17-000027",
                                     "end":  "2015-01-25",
                                     "filed":  "2017-03-01",
                                     "form":  "10-K",
                                     "tag":  "WeightedAverageNumberOfDilutedSharesOutstanding",
                                     "unit":  "shares",
                                     "val":  563000000
                                 },
                                 {
                                     "accn":  "0001045810-18-000010",
                                     "end":  "2016-01-31",
                                     "filed":  "2018-02-28",
                                     "form":  "10-K",
                                     "tag":  "WeightedAverageNumberOfDilutedSharesOutstanding",
                                     "unit":  "shares",
                                     "val":  569000000
                                 },
                                 {
                                     "accn":  "0001045810-19-000023",
                                     "end":  "2017-01-29",
                                     "filed":  "2019-02-21",
                                     "form":  "10-K",
                                     "tag":  "WeightedAverageNumberOfDilutedSharesOutstanding",
                                     "unit":  "shares",
                                     "val":  649000000
                                 },
                                 {
                                     "accn":  "0001045810-20-000010",
                                     "end":  "2018-01-28",
                                     "filed":  "2020-02-20",
                                     "form":  "10-K",
                                     "tag":  "WeightedAverageNumberOfDilutedSharesOutstanding",
                                     "unit":  "shares",
                                     "val":  632000000
                                 },
                                 {
                                     "accn":  "0001045810-21-000010",
                                     "end":  "2019-01-27",
                                     "filed":  "2021-02-26",
                                     "form":  "10-K",
                                     "tag":  "WeightedAverageNumberOfDilutedSharesOutstanding",
                                     "unit":  "shares",
                                     "val":  625000000
                                 },
                                 {
                                     "accn":  "0001045810-22-000036",
                                     "end":  "2020-01-26",
                                     "filed":  "2022-03-18",
                                     "form":  "10-K",
                                     "tag":  "WeightedAverageNumberOfDilutedSharesOutstanding",
                                     "unit":  "shares",
                                     "val":  2472000000
                                 },
                                 {
                                     "accn":  "0001045810-23-000017",
                                     "end":  "2021-01-31",
                                     "filed":  "2023-02-24",
                                     "form":  "10-K",
                                     "tag":  "WeightedAverageNumberOfDilutedSharesOutstanding",
                                     "unit":  "shares",
                                     "val":  2510000000
                                 },
                                 {
                                     "accn":  "0001045810-24-000029",
                                     "end":  "2022-01-30",
                                     "filed":  "2024-02-21",
                                     "form":  "10-K",
                                     "tag":  "WeightedAverageNumberOfDilutedSharesOutstanding",
                                     "unit":  "shares",
                                     "val":  2535000000
                                 },
                                 {
                                     "accn":  "0001045810-25-000023",
                                     "end":  "2023-01-29",
                                     "filed":  "2025-02-26",
                                     "form":  "10-K",
                                     "tag":  "WeightedAverageNumberOfDilutedSharesOutstanding",
                                     "unit":  "shares",
                                     "val":  25070000000
                                 },
                                 {
                                     "accn":  "0001045810-26-000021",
                                     "end":  "2024-01-28",
                                     "filed":  "2026-02-25",
                                     "form":  "10-K",
                                     "tag":  "WeightedAverageNumberOfDilutedSharesOutstanding",
                                     "unit":  "shares",
                                     "val":  24940000000
                                 },
                                 {
                                     "accn":  "0001045810-26-000021",
                                     "end":  "2025-01-26",
                                     "filed":  "2026-02-25",
                                     "form":  "10-K",
                                     "tag":  "WeightedAverageNumberOfDilutedSharesOutstanding",
                                     "unit":  "shares",
                                     "val":  24804000000
                                 },
                                 {
                                     "accn":  "0001045810-26-000021",
                                     "end":  "2026-01-25",
                                     "filed":  "2026-02-25",
                                     "form":  "10-K",
                                     "tag":  "WeightedAverageNumberOfDilutedSharesOutstanding",
                                     "unit":  "shares",
                                     "val":  24514000000
                                 }
                             ],
    "short_term_investments":  49122000000,
    "short_term_investments_audit":  {
                                         "accn":  "0001045810-25-000230",
                                         "end":  "2025-10-26",
                                         "filed":  "2025-11-19",
                                         "val":  49122000000
                                     },
    "total_debt":  8470000000
}
PS C:\Users\zhadr> Invoke-RestMethod -Method Post -Uri "https://growth-enrich-python-production.up.railway.app/price_on_date" -ContentType "application/json" -Body '{"ticker":"NVDA","date":"2020-03-23","eps":6.63}' | ConvertTo-Json -Depth 6
Invoke-RestMethod :
404 Not Found
Not Found
The requested URL was not found on the server. If you entered the URL manually please check your spelling and try again
.
строка:1 знак:1
+ Invoke-RestMethod -Method Post -Uri "https://growth-enrich-python-pro ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : InvalidOperation: (System.Net.HttpWebRequest:HttpWebRequest) [Invoke-RestMethod], WebExc
   eption
    + FullyQualifiedErrorId : WebCmdletWebResponseException,Microsoft.PowerShell.Commands.InvokeRestMethodCommand
Windows PowerShell
Copyright (C) Microsoft Corporation. All rights reserved.

PS C:\Users\zhadr> Invoke-RestMethod -Method Post -Uri "https://growth-enrich-python-production.up.railway.app/price_on_date" -ContentType "application/json" -Body '{"ticker":"NVDA","date":"2020-03-23","eps":6.63}' | ConvertTo-Json -Depth 6

{
    "_errors":  {
                    "pe_same_share_basis_NVDA":  "split_factor_undeterminable: close/adjClose ratio 40.2006 matches no clean split multiple and is not ~1.0",
                    "split_factor_NVDA":  "split_factor_undeterminable: close/adjClose ratio 40.2006 matches no clean split multiple and is not ~1.0"
                },
    "date":  "2020-03-23",
    "pe_same_share_basis":  null,
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
    "split_factor":  null,
    "ticker":  "NVDA"
}
PS C:\Users\zhadr> Invoke-RestMethod -Method Post -Uri "https://growth-enrich-python-production.up.railway.app/edgar_facts" -ContentType "application/json" -Body '{"ticker":"NVDA","as_of":"2020-03-23"}' | ConvertTo-Json -Depth 6
{
    "_as_of":  "2020-03-23",
    "_cik":  "0001045810",
    "_entity_name":  "NVIDIA CORP",
    "_errors":  {

                },
    "_field_sources":  {
                           "capex":  [
                                         "PaymentsToAcquirePropertyPlantAndEquipment"
                                     ],
                           "cash":  "CashAndCashEquivalentsAtCarryingValue",
                           "dividends_paid":  [
                                                  "PaymentsOfDividends"
                                              ],
                           "dps":  [
                                       "CommonStockDividendsPerShareCashPaid"
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
                                           "RevenueFromContractWithCustomerExcludingAssessedTax",
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
                           "stockholders_equity":  "StockholdersEquity",
                           "total_debt":  "LongTermDebt"
                       },
    "_flags":  {
                   "confirmed_splits_none":  "no retroactive share-count restatement found in companyfacts+companyconcept 10-K history; a clean ratio jump downstream is UNCONFIRMED, not proven dilution",
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
                                                      }
                                                  ],
                   "series_discontinuity_provenance":  [
                                                           {
                                                               "cosignal_changed":  [
                                                                                        "accession"
                                                                                    ],
                                                               "end":  "2017-01-29",
                                                               "jump_pct":  87.7,
                                                               "prev_end":  "2016-01-31",
                                                               "prev_ratio":  0.1491,
                                                               "prev_tag":  "Revenues",
                                                               "provenance_changed":  [
                                                                                          "tag"
                                                                                      ],
                                                               "provenance_uncomparable":  [

                                                                                           ],
                                                               "ratio":  0.2799,
                                                               "tag":  "RevenueFromContractWithCustomerExcludingAssessedTax"
                                                           }
                                                       ],
                   "series_tag_mixed":  {
                                            "revenue":  {
                                                            "2008":  "Revenues",
                                                            "2009":  "Revenues",
                                                            "2010":  "Revenues",
                                                            "2011":  "Revenues",
                                                            "2012":  "Revenues",
                                                            "2013":  "Revenues",
                                                            "2014":  "Revenues",
                                                            "2015":  "Revenues",
                                                            "2016":  "Revenues",
                                                            "2017":  "RevenueFromContractWithCustomerExcludingAssessedTax",
                                                            "2018":  "RevenueFromContractWithCustomerExcludingAssessedTax",
                                                            "2019":  "RevenueFromContractWithCustomerExcludingAssessedTax",
                                                            "2020":  "RevenueFromContractWithCustomerExcludingAssessedTax"
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
                                                        "absent_years":  [
                                                                             "2011",
                                                                             "2012"
                                                                         ],
                                                        "chosen_tag":  "CommonStockDividendsPerShareCashPaid",
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
                        }
                    ],
    "cash":  10896000000,
    "cash_audit":  {
                       "accn":  "0001045810-20-000010",
                       "end":  "2020-01-26",
                       "filed":  "2020-02-20",
                       "val":  10896000000
                   },
    "current_portion_debt":  null,
    "current_portion_debt_audit":  null,
    "debt_components_tags":  {
                                 "components_complete":  false,
                                 "current_maturities":  null,
                                 "full_long_term_debt":  "LongTermDebt",
                                 "noncurrent":  null
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
                                     "accn":  "0001045810-20-000010",
                                     "end":  "2019-01-27",
                                     "filed":  "2020-02-20",
                                     "form":  "10-K",
                                     "tag":  "PaymentsOfDividends",
                                     "unit":  "USD",
                                     "val":  371000000
                                 },
                                 {
                                     "accn":  "0001045810-20-000010",
                                     "end":  "2020-01-26",
                                     "filed":  "2020-02-20",
                                     "form":  "10-K",
                                     "tag":  "PaymentsOfDividends",
                                     "unit":  "USD",
                                     "val":  390000000
                                 }
                             ],
    "dps":  [
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
                    "val":  0.395
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
                    "val":  0.64
                }
            ],
    "dps_audit":  [
                      {
                          "accn":  "0001045810-15-000036",
                          "end":  "2013-01-27",
                          "filed":  "2015-03-12",
                          "form":  "10-K",
                          "tag":  "CommonStockDividendsPerShareCashPaid",
                          "unit":  "USD/shares",
                          "val":  0.075
                      },
                      {
                          "accn":  "0001045810-16-000205",
                          "end":  "2014-01-26",
                          "filed":  "2016-03-17",
                          "form":  "10-K",
                          "tag":  "CommonStockDividendsPerShareCashPaid",
                          "unit":  "USD/shares",
                          "val":  0.31
                      },
                      {
                          "accn":  "0001045810-17-000027",
                          "end":  "2015-01-25",
                          "filed":  "2017-03-01",
                          "form":  "10-K",
                          "tag":  "CommonStockDividendsPerShareCashPaid",
                          "unit":  "USD/shares",
                          "val":  0.34
                      },
                      {
                          "accn":  "0001045810-18-000010",
                          "end":  "2016-01-31",
                          "filed":  "2018-02-28",
                          "form":  "10-K",
                          "tag":  "CommonStockDividendsPerShareCashPaid",
                          "unit":  "USD/shares",
                          "val":  0.395
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
                          "accn":  "0001045810-20-000010",
                          "end":  "2019-01-27",
                          "filed":  "2020-02-20",
                          "form":  "10-K",
                          "tag":  "CommonStockDividendsPerShareCashPaid",
                          "unit":  "USD/shares",
                          "val":  0.61
                      },
                      {
                          "accn":  "0001045810-20-000010",
                          "end":  "2020-01-26",
                          "filed":  "2020-02-20",
                          "form":  "10-K",
                          "tag":  "CommonStockDividendsPerShareCashPaid",
                          "unit":  "USD/shares",
                          "val":  0.64
                      }
                  ],
    "dps_series":  [
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
                           "val":  0.395
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
                           "val":  0.64
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
                                   "accn":  "0001045810-20-000010",
                                   "end":  "2019-01-27",
                                   "filed":  "2020-02-20",
                                   "form":  "10-K",
                                   "tag":  "GrossProfit",
                                   "unit":  "USD",
                                   "val":  7171000000
                               },
                               {
                                   "accn":  "0001045810-20-000010",
                                   "end":  "2020-01-26",
                                   "filed":  "2020-02-20",
                                   "form":  "10-K",
                                   "tag":  "GrossProfit",
                                   "unit":  "USD",
                                   "val":  6768000000
                               }
                           ],
    "long_term_debt":  1991000000,
    "long_term_debt_audit":  {
                                 "accn":  "0001045810-20-000010",
                                 "end":  "2020-01-26",
                                 "filed":  "2020-02-20",
                                 "val":  1991000000
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
                                 "accn":  "0001045810-20-000010",
                                 "end":  "2019-01-27",
                                 "filed":  "2020-02-20",
                                 "form":  "10-K",
                                 "tag":  "NetIncomeLoss",
                                 "unit":  "USD",
                                 "val":  4141000000
                             },
                             {
                                 "accn":  "0001045810-20-000010",
                                 "end":  "2020-01-26",
                                 "filed":  "2020-02-20",
                                 "form":  "10-K",
                                 "tag":  "NetIncomeLoss",
                                 "unit":  "USD",
                                 "val":  2796000000
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
                          "accn":  "0001045810-20-000010",
                          "end":  "2019-01-27",
                          "filed":  "2020-02-20",
                          "form":  "10-K",
                          "tag":  "NetCashProvidedByUsedInOperatingActivities",
                          "unit":  "USD",
                          "val":  3743000000
                      },
                      {
                          "accn":  "0001045810-20-000010",
                          "end":  "2020-01-26",
                          "filed":  "2020-02-20",
                          "form":  "10-K",
                          "tag":  "NetCashProvidedByUsedInOperatingActivities",
                          "unit":  "USD",
                          "val":  4761000000
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
                                       "accn":  "0001045810-20-000010",
                                       "end":  "2019-01-27",
                                       "filed":  "2020-02-20",
                                       "form":  "10-K",
                                       "tag":  "OperatingIncomeLoss",
                                       "unit":  "USD",
                                       "val":  3804000000
                                   },
                                   {
                                       "accn":  "0001045810-20-000010",
                                       "end":  "2020-01-26",
                                       "filed":  "2020-02-20",
                                       "form":  "10-K",
                                       "tag":  "OperatingIncomeLoss",
                                       "unit":  "USD",
                                       "val":  2846000000
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
                        "end":  "2019-01-27",
                        "val":  11716000000
                    },
                    {
                        "end":  "2020-01-26",
                        "val":  10918000000
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
                              "accn":  "0001045810-19-000023",
                              "end":  "2017-01-29",
                              "filed":  "2019-02-21",
                              "form":  "10-K",
                              "tag":  "RevenueFromContractWithCustomerExcludingAssessedTax",
                              "unit":  "USD",
                              "val":  6910000000
                          },
                          {
                              "accn":  "0001045810-20-000010",
                              "end":  "2018-01-28",
                              "filed":  "2020-02-20",
                              "form":  "10-K",
                              "tag":  "RevenueFromContractWithCustomerExcludingAssessedTax",
                              "unit":  "USD",
                              "val":  9714000000
                          },
                          {
                              "accn":  "0001045810-20-000010",
                              "end":  "2019-01-27",
                              "filed":  "2020-02-20",
                              "form":  "10-K",
                              "tag":  "RevenueFromContractWithCustomerExcludingAssessedTax",
                              "unit":  "USD",
                              "val":  11716000000
                          },
                          {
                              "accn":  "0001045810-20-000010",
                              "end":  "2020-01-26",
                              "filed":  "2020-02-20",
                              "form":  "10-K",
                              "tag":  "RevenueFromContractWithCustomerExcludingAssessedTax",
                              "unit":  "USD",
                              "val":  10918000000
                          }
                      ],
    "roe_basis":  "net_income / year_end_equity",
    "roe_median_5y":  0.28913571676501215,
    "rpo":  364000000,
    "rpo_audit":  {
                      "accn":  "0001045810-20-000010",
                      "end":  "2020-01-26",
                      "filed":  "2020-02-20",
                      "val":  364000000
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
                          "accn":  "0001045810-20-000010",
                          "end":  "2019-01-27",
                          "filed":  "2020-02-20",
                          "form":  "10-K",
                          "tag":  "ShareBasedCompensation",
                          "unit":  "USD",
                          "val":  557000000
                      },
                      {
                          "accn":  "0001045810-20-000010",
                          "end":  "2020-01-26",
                          "filed":  "2020-02-20",
                          "form":  "10-K",
                          "tag":  "ShareBasedCompensation",
                          "unit":  "USD",
                          "val":  844000000
                      }
                  ],
    "shares_current":  612000000,
    "shares_current_audit":  {
                                 "accn":  "0001045810-20-000010",
                                 "end":  "2020-02-14",
                                 "filed":  "2020-02-20",
                                 "val":  612000000
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
                               "val":  618000000
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
                                     "accn":  "0001045810-20-000010",
                                     "end":  "2019-01-27",
                                     "filed":  "2020-02-20",
                                     "form":  "10-K",
                                     "tag":  "WeightedAverageNumberOfDilutedSharesOutstanding",
                                     "unit":  "shares",
                                     "val":  625000000
                                 },
                                 {
                                     "accn":  "0001045810-20-000010",
                                     "end":  "2020-01-26",
                                     "filed":  "2020-02-20",
                                     "form":  "10-K",
                                     "tag":  "WeightedAverageNumberOfDilutedSharesOutstanding",
                                     "unit":  "shares",
                                     "val":  618000000
                                 }
                             ],
    "short_term_investments":  1000000,
    "short_term_investments_audit":  {
                                         "accn":  "0001045810-20-000010",
                                         "end":  "2020-01-26",
                                         "filed":  "2020-02-20",
                                         "val":  1000000
                                     },
    "stockholders_equity":  [
                                {
                                    "end":  "2007-01-28",
                                    "val":  2006919000
                                },
                                {
                                    "end":  "2008-01-27",
                                    "val":  2617912000
                                },
                                {
                                    "end":  "2009-01-25",
                                    "val":  2394652000
                                },
                                {
                                    "end":  "2010-01-31",
                                    "val":  2665140000
                                },
                                {
                                    "end":  "2011-01-30",
                                    "val":  3181462000
                                },
                                {
                                    "end":  "2012-01-29",
                                    "val":  4145724000
                                },
                                {
                                    "end":  "2013-01-27",
                                    "val":  4827000000
                                },
                                {
                                    "end":  "2014-01-26",
                                    "val":  4455000000
                                },
                                {
                                    "end":  "2015-01-25",
                                    "val":  4418000000
                                },
                                {
                                    "end":  "2016-01-31",
                                    "val":  4469000000
                                },
                                {
                                    "end":  "2017-01-29",
                                    "val":  5762000000
                                },
                                {
                                    "end":  "2018-01-28",
                                    "val":  7471000000
                                },
                                {
                                    "end":  "2019-01-27",
                                    "val":  9342000000
                                },
                                {
                                    "end":  "2020-01-26",
                                    "val":  12204000000
                                }
                            ],
    "stockholders_equity_audit":  [
                                      {
                                          "accn":  "0001045810-10-000006",
                                          "end":  "2007-01-28",
                                          "filed":  "2010-03-18",
                                          "tag":  "StockholdersEquity",
                                          "val":  2006919000
                                      },
                                      {
                                          "accn":  "0001045810-11-000015",
                                          "end":  "2008-01-27",
                                          "filed":  "2011-03-16",
                                          "tag":  "StockholdersEquity",
                                          "val":  2617912000
                                      },
                                      {
                                          "accn":  "0001045810-12-000013",
                                          "end":  "2009-01-25",
                                          "filed":  "2012-03-13",
                                          "tag":  "StockholdersEquity",
                                          "val":  2394652000
                                      },
                                      {
                                          "accn":  "0001045810-13-000008",
                                          "end":  "2010-01-31",
                                          "filed":  "2013-03-12",
                                          "tag":  "StockholdersEquity",
                                          "val":  2665140000
                                      },
                                      {
                                          "accn":  "0001045810-14-000030",
                                          "end":  "2011-01-30",
                                          "filed":  "2014-03-13",
                                          "tag":  "StockholdersEquity",
                                          "val":  3181462000
                                      },
                                      {
                                          "accn":  "0001045810-15-000036",
                                          "end":  "2012-01-29",
                                          "filed":  "2015-03-12",
                                          "tag":  "StockholdersEquity",
                                          "val":  4145724000
                                      },
                                      {
                                          "accn":  "0001045810-16-000205",
                                          "end":  "2013-01-27",
                                          "filed":  "2016-03-17",
                                          "tag":  "StockholdersEquity",
                                          "val":  4827000000
                                      },
                                      {
                                          "accn":  "0001045810-17-000027",
                                          "end":  "2014-01-26",
                                          "filed":  "2017-03-01",
                                          "tag":  "StockholdersEquity",
                                          "val":  4455000000
                                      },
                                      {
                                          "accn":  "0001045810-18-000010",
                                          "end":  "2015-01-25",
                                          "filed":  "2018-02-28",
                                          "tag":  "StockholdersEquity",
                                          "val":  4418000000
                                      },
                                      {
                                          "accn":  "0001045810-19-000023",
                                          "end":  "2016-01-31",
                                          "filed":  "2019-02-21",
                                          "tag":  "StockholdersEquity",
                                          "val":  4469000000
                                      },
                                      {
                                          "accn":  "0001045810-20-000010",
                                          "end":  "2017-01-29",
                                          "filed":  "2020-02-20",
                                          "tag":  "StockholdersEquity",
                                          "val":  5762000000
                                      },
                                      {
                                          "accn":  "0001045810-20-000010",
                                          "end":  "2018-01-28",
                                          "filed":  "2020-02-20",
                                          "tag":  "StockholdersEquity",
                                          "val":  7471000000
                                      },
                                      {
                                          "accn":  "0001045810-20-000010",
                                          "end":  "2019-01-27",
                                          "filed":  "2020-02-20",
                                          "tag":  "StockholdersEquity",
                                          "val":  9342000000
                                      },
                                      {
                                          "accn":  "0001045810-20-000010",
                                          "end":  "2020-01-26",
                                          "filed":  "2020-02-20",
                                          "tag":  "StockholdersEquity",
                                          "val":  12204000000
                                      }
                                  ],
    "total_debt":  1991000000
}
PS C:\Users\zhadr>
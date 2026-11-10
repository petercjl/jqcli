# Automated platform route
Discover precise help before unfamiliar flags. `jqcli --format json auth status` checks credentials without exposing values. Configuration is external; authorizing a strategy/backtest task authorizes the specified upload/run, not deletion or paid credits.

Use strategy ls/show to locate exact target and read current source; new/edit take --file SOURCE. A named user's existing strategy is never a temporary smoke asset. Preserve original source and requested parameters. `backtest run ID --start DATE --end DATE --capital AMOUNT --freq day|minute --wait` waits with bounded timeout; --compile is a separate compilation mode. Do not add --use-credit without paid-action permission. On timeout inspect the same backtest ID.

Read backtest show/stats/result/logs/positions/transactions with the actual ID. Errors precede performance interpretation. `backtest export ID --mode all --output-dir NEW_DIR` downloads result CSV, transaction ZIP, position ZIP and log ZIP, then preprocesses normalized UTF-8 data. Inspect live export help for exact current output option. --mode preprocess operates on already downloaded files without a new platform run.

Authentication/permission failures return to account setup. Unexpected redirects or system-busy replies are not empty strategy data. Record partial coverage and avoid blind duplicate uploads/runs. Outputs retain raw exports alongside normalized files. Return to result analysis or code repair.

Detail transactions/positions default to one page. For complete read-only comparisons use --all; pagination follows offset/dateOffset, overlaps boundary dates and spaces requests by 2–3 seconds. Stalled or incomplete boundaries raise explicit errors. These commands do not create ZIP export tasks or enable credit spending.


## Same-day simulated quantities

Use `live holdings --name NAME --date YYYY-MM-DD --limit 10000` for current
quantities and `live transactions` for full order/fill evidence. Both default to
`--source api`: authenticated HTTP requests using the external CLI token/cookie,
without a browser, CDP, page selection or DOM parsing. Exact-name matches take priority;
an ambiguous name fails. Resolve names for each run because encrypted IDs rotate.

The read-only endpoints are `/algorithm/live/position` and
`/algorithm/live/transactionDetail`. A successful response requires the platform's OK
envelope, an explicit array, `isLimit=false` and a result below the requested transaction
cap. Saturated/truncated or malformed results raise `INTRADAY_INCOMPLETE_INPUT`; raise the
limit within CLI bounds rather than assuming pagination. Historical dates are supported.
Two position and transaction reads must match before reconstruction; changes raise
`INTRADAY_SOURCE_CHANGED_DURING_READ` and the caller may retry within its bounded budget.

Repeated codes are aggregated. Sell quantities and values normalize negative magnitudes;
contradictory buy signs fail. Only full fills strictly after the timestamped same-day
snapshot boundary are replayed; older fills are already included. Orders spanning or on
the boundary, partial fills, duplicate indistinguishable fills, missing dates/fees and
negative reconstructed positions stop reconstruction. An empty position snapshot without
a reliable baseline timestamp remains unsupported. Do not infer zero holdings from it.

Output includes baseline/query/fill times, full transactions and HTTP provenance. Cash
reconstruction assumes no transfers; current prices, values, weights and sellability are
null. Refresh comparable prices separately when valuation is needed.

For explicit browser verification use `--source page`. Keep exactly one matching logged-in
live page open in local Chrome (CDP 9222/9223 or `JQCLI_CDP_URL`). This branch reloads and
reads the page's fully loaded holdings and transaction grids. It never silently replaces
a failed API request. Login and permission failures return to authentication; neither
transport starts a backtest or submits an order. Return to result reporting.

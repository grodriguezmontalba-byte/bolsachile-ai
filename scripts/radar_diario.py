    )

    portfolio["diagnostics"] = diagnostics

    return portfolio


def main():
    actions = []
    histories = {}

    for symbol in SYMBOLS:
        try:
            df = prices(symbol)
            histories[symbol] = df

            action = analyze(symbol, df)

            print(
                symbol,
                "OK",
                action["date"],
                "|",
                action["entry_reason"]
            )

        except Exception as exc:
            action = {
                "symbol": symbol,
                "status": "unavailable",
                "reason": str(exc)[:180]
            }

            print(
                symbol,
                "UNAVAILABLE",
                str(exc)[:100]
            )

        actions.append(action)

    portfolio = simulate(
        read_portfolio(), actions, histories
    )

    payload = {
        "updated_at": (
            datetime.now(timezone.utc).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        ),
        "source": (
            "Yahoo Finance vía yfinance (no oficial)"
        ),
        "mode": "virtual",
        "initial_capital_clp": CAPITAL,
        "method": (
            "MA20/MA60, prueba cronológica 40%, "
            "horizontes 5/10/20/40 sesiones"
        ),
        "assumed_fee_per_side": FEE,
        "assumed_spread_roundtrip": SPREAD,
        "disclaimer": (
            "Simulación educativa; resultados "
            "exploratorios, no probabilidades predictivas."
        ),
        "actions": actions,
        "latest_close_date": max(
            (a["date"] for a in actions if a["status"] == "ok"),
            default=None
        ),
        "data_dates_by_symbol": {
            a["symbol"]: a["date"]
            for a in actions if a["status"] == "ok"
        }
    }

    (DATA / "market.json").write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            allow_nan=False
        ) + "\n",
        encoding="utf-8"
    )

    (DATA / "portfolio.json").write_text(
        json.dumps(
            portfolio,
            ensure_ascii=False,
            indent=2,
            allow_nan=False
        ) + "\n",
        encoding="utf-8"
    )

    print(
        "Disponibles:",
        sum(
            a["status"] == "ok"
            for a in actions
        ),
        "| Operaciones acumuladas:",
        len(portfolio["trades"])
    )

    print(
        "Último cierre disponible:",
        payload["latest_close_date"],
        "| Fecha UTC de ejecución:",
        datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    )

    print(
        "Diagnóstico:",
        " | ".join(
            portfolio.get("diagnostics", [])
        )
    )


if __name__ == "__main__":
    main()

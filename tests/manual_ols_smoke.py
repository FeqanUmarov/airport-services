"""Manual OLS smoke test (shared full OLS scenario)."""

import asyncio

from tests.ols_generation_smoke import main


if __name__ == "__main__":
    asyncio.run(main())

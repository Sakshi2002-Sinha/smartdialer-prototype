
from smartdialer.simulator.scenarios import (
    print_results,
    run_default_simulation,
)


def main():
    results = run_default_simulation()
    print_results(results)


if __name__ == "__main__":
    main()

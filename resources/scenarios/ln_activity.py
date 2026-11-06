#!/usr/bin/env python3

import secrets
import threading
from random import randint, sample
from time import sleep

from commander import Commander


class LNActivity(Commander):
    def set_test_params(self):
        self.num_nodes = None

    def add_options(self, parser):
        parser.description = (
            "Pay invoices between random LN nodes from many threads at once, "
            "creating a storm of parallel LN payments"
        )
        parser.usage = "warnet run /path/to/ln_activity.py [options]"
        parser.add_argument(
            "--threads",
            dest="threads",
            default=10,
            type=int,
            help="Number of threads sending payments in parallel (default 10)",
        )
        parser.add_argument(
            "--interval",
            dest="interval",
            default=1,
            type=float,
            help="Seconds each thread waits between payments (default 1)",
        )
        parser.add_argument(
            "--min-amount",
            dest="min_amount",
            default=1000,
            type=int,
            help="Minimum payment amount in sats (default 1000)",
        )
        parser.add_argument(
            "--max-amount",
            dest="max_amount",
            default=10000,
            type=int,
            help="Maximum payment amount in sats (default 10000)",
        )
        parser.add_argument(
            "--payments",
            dest="payments",
            default=0,
            type=int,
            help="Number of payments each thread sends, 0 to run forever (default 0)",
        )

    def pay_random(self, thread_id):
        lns = list(self.lns.values())
        count = 0
        while self.options.payments == 0 or count < self.options.payments:
            count += 1
            src, tgt = sample(lns, 2)
            amount = randint(self.options.min_amount, self.options.max_amount)
            # CLN requires invoice labels to be unique
            label = f"ln_activity-{thread_id}-{count}-{secrets.token_hex(4)}"
            log = f"thread {thread_id}: {src.name} -> {tgt.name} {amount} sats"
            try:
                invoice = tgt.createinvoice(amount, label)
                # Each implementation returns something different, e.g. a payment id
                # or status, some before the payment has completed
                res = src.payinvoice(invoice)
                self.log.info(f"{log}: {str(res)[:120]}")
            except Exception as e:
                self.log.info(f"{log}: FAILED {e}")
            sleep(self.options.interval)

    def run_test(self):
        if len(self.lns) < 2:
            raise Exception(f"Need at least 2 LN nodes, found {len(self.lns)}")
        self.log.info(
            f"Starting {self.options.threads} payment threads between {len(self.lns)} LN nodes"
        )
        threads = []
        for i in range(self.options.threads):
            t = threading.Thread(target=self.pay_random, args=(i,))
            t.start()
            threads.append(t)
        all(thread.join() is None for thread in threads)


def main():
    LNActivity("").main()


if __name__ == "__main__":
    main()

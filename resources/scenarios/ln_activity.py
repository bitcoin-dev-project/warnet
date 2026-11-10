#!/usr/bin/env python3

import re
import secrets
import threading
from collections import Counter
from random import randint, sample
from time import sleep, time

from commander import Commander


class PaymentStats:
    """Payment results from all threads, grouped by sender and receiver implementation"""

    def __init__(self):
        self.lock = threading.Lock()
        self.start = time()
        self.attempted = Counter()
        self.succeeded = Counter()
        self.success_seconds = Counter()
        self.reasons = Counter()
        self.reason_examples = {}
        self.sender_failures = Counter()
        self.receiver_failures = Counter()

    @staticmethod
    def normalize(reason):
        # Group failures that only differ by ids or amounts
        reason = re.sub(r"\b[0-9a-fA-F]{16,}\b", "<id>", reason)
        reason = re.sub(r"\d+", "N", reason)
        return reason[:200]

    def record(self, src, tgt, amount, succeeded, reason, seconds):
        pair = f"{src.impl} -> {tgt.impl}"
        with self.lock:
            self.attempted[pair] += 1
            if succeeded:
                self.succeeded[pair] += 1
                self.success_seconds[pair] += seconds
                return
            key = (pair, self.normalize(reason))
            self.reasons[key] += 1
            self.reason_examples.setdefault(
                key, f"{src.name} -> {tgt.name} {amount} sats: {reason[:300]}"
            )
            self.sender_failures[f"{src.name} ({src.impl})"] += 1
            self.receiver_failures[f"{tgt.name} ({tgt.impl})"] += 1

    def report(self):
        with self.lock:
            attempted = sum(self.attempted.values())
            succeeded = sum(self.succeeded.values())
            failed = attempted - succeeded
            elapsed = int(time() - self.start)
            lines = [
                f"Payment report after {elapsed // 60}m{elapsed % 60:02d}s: {attempted} attempted, "
                f"{succeeded} succeeded, {failed} failed ({percent(failed, attempted)} failed)"
            ]
            if attempted:
                lines.append("  By sender -> receiver implementation:")
            for pair in sorted(self.attempted):
                pair_attempted = self.attempted[pair]
                pair_succeeded = self.succeeded[pair]
                pair_failed = pair_attempted - pair_succeeded
                avg = (
                    f", {self.success_seconds[pair] / pair_succeeded:.1f}s avg success"
                    if pair_succeeded
                    else ""
                )
                lines.append(
                    f"    {pair:<16} {pair_attempted:>6} attempted, {pair_succeeded:>6} succeeded, "
                    f"{pair_failed:>6} failed ({percent(pair_failed, pair_attempted)}){avg}"
                )
            if self.reasons:
                lines.append("  Failure reasons:")
            for (pair, reason), count in self.reasons.most_common():
                lines.append(f"    {count:>6}x {pair}: {reason}")
                lines.append(f"            e.g. {self.reason_examples[(pair, reason)]}")
            if self.sender_failures:
                lines.append("  Most failures as sender: " + top(self.sender_failures))
                lines.append("  Most failures as receiver: " + top(self.receiver_failures))
            return "\n".join(lines)


def percent(part, total):
    return f"{100 * part / total:.1f}%" if total else "0.0%"


def top(counter, n=5):
    return ", ".join(f"{name} {count}" for name, count in counter.most_common(n))


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
        parser.add_argument(
            "--report-interval",
            dest="report_interval",
            default=60,
            type=float,
            help="Seconds between payment statistics reports (default 60)",
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
            log = f"thread {thread_id}: {src.name} ({src.impl}) -> {tgt.name} ({tgt.impl}) {amount} sats"
            start = time()
            try:
                invoice = tgt.createinvoice(amount, label)
            except Exception as e:
                reason = f"createinvoice failed: {e}"
                succeeded = False
            else:
                try:
                    # Waits until the payment succeeded or failed
                    succeeded, reason = src.pay(invoice)
                except Exception as e:
                    succeeded, reason = False, f"pay failed: {e}"
            seconds = time() - start
            self.stats.record(src, tgt, amount, succeeded, reason, seconds)
            if succeeded:
                self.log.info(f"{log}: succeeded in {seconds:.1f}s")
            else:
                self.log.info(f"{log}: FAILED {reason}")
            sleep(self.options.interval)

    def run_test(self):
        if len(self.lns) < 2:
            raise Exception(f"Need at least 2 LN nodes, found {len(self.lns)}")
        self.log.info(
            f"Starting {self.options.threads} payment threads between {len(self.lns)} LN nodes"
        )
        self.stats = PaymentStats()
        threads = []
        for i in range(self.options.threads):
            t = threading.Thread(target=self.pay_random, args=(i,))
            t.start()
            threads.append(t)
        next_report = time() + self.options.report_interval
        while any(thread.is_alive() for thread in threads):
            sleep(1)
            if time() >= next_report:
                self.log.info(self.stats.report())
                next_report += self.options.report_interval
        self.log.info(self.stats.report())


def main():
    LNActivity("").main()


if __name__ == "__main__":
    main()

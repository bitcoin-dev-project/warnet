#!/usr/bin/env python3

import re
import secrets
import threading
from collections import Counter, defaultdict
from random import randint, sample
from time import sleep, time

from commander import Commander


class Payments:
    """Count, amount range and hop counts of a group of payments"""

    def __init__(self):
        self.count = 0
        self.min_amount = None
        self.max_amount = None
        self.hops = Counter()
        self.seconds = 0

    def add(self, amount, hops, seconds):
        self.count += 1
        self.min_amount = amount if self.min_amount is None else min(self.min_amount, amount)
        self.max_amount = amount if self.max_amount is None else max(self.max_amount, amount)
        self.hops["?" if hops is None else hops] += 1
        self.seconds += seconds

    def summary(self):
        # Known hop counts in order, then unknown
        hops = sorted(self.hops, key=lambda h: (h == "?", h if h != "?" else 0))
        hops_str = " ".join(f"{h}:{self.hops[h]}" for h in hops)
        return (
            f"{self.min_amount:,}-{self.max_amount:,} sats, hops (hops:payments) {hops_str}, "
            f"{self.seconds / self.count:.1f}s avg"
        )


class PaymentStats:
    """Payment results from all threads, grouped by sender and receiver implementation"""

    def __init__(self):
        self.lock = threading.Lock()
        self.start = time()
        self.succeeded = defaultdict(Payments)
        self.failed = defaultdict(Payments)
        self.reasons = defaultdict(Payments)
        self.reason_examples = {}
        self.sender_failures = Counter()
        self.receiver_failures = Counter()

    @staticmethod
    def normalize(reason):
        # Group failures that only differ by ids or amounts
        reason = re.sub(r"\b[0-9a-fA-F]{16,}\b", "<id>", reason)
        reason = re.sub(r"\d+", "N", reason)
        return reason[:200]

    def record(self, src, tgt, amount, succeeded, reason, hops, seconds):
        pair = f"{src.impl} -> {tgt.impl}"
        with self.lock:
            if succeeded:
                self.succeeded[pair].add(amount, hops, seconds)
                return
            self.failed[pair].add(amount, hops, seconds)
            key = (pair, self.normalize(reason))
            self.reasons[key].add(amount, hops, seconds)
            self.reason_examples.setdefault(
                key, f"{src.name} -> {tgt.name} {amount} sats: {reason[:300]}"
            )
            self.sender_failures[f"{src.name} ({src.impl})"] += 1
            self.receiver_failures[f"{tgt.name} ({tgt.impl})"] += 1

    def report(self):
        with self.lock:
            succeeded = sum(p.count for p in self.succeeded.values())
            failed = sum(p.count for p in self.failed.values())
            attempted = succeeded + failed
            elapsed = int(time() - self.start)
            lines = [
                f"Payment report after {elapsed // 60}m{elapsed % 60:02d}s: {attempted} attempted, "
                f"{succeeded} succeeded, {failed} failed ({percent(failed, attempted)} failed)"
            ]
            pairs = sorted(set(self.succeeded) | set(self.failed))
            if pairs:
                lines.append("  By sender -> receiver implementation:")
            for pair in pairs:
                ok = self.succeeded.get(pair)
                bad = self.failed.get(pair)
                ok_count = ok.count if ok else 0
                bad_count = bad.count if bad else 0
                lines.append(
                    f"    {pair}: {ok_count + bad_count} attempted, "
                    f"{bad_count} failed ({percent(bad_count, ok_count + bad_count)})"
                )
                if ok:
                    lines.append(f"      succeeded {ok_count:>6}: {ok.summary()}")
                if bad:
                    lines.append(f"      failed    {bad_count:>6}: {bad.summary()}")
            if self.reasons:
                lines.append("  Failure reasons:")
            for key, payments in sorted(self.reasons.items(), key=lambda kv: -kv[1].count):
                pair, reason = key
                lines.append(f"    {payments.count:>6}x {pair}: {reason}")
                lines.append(f"            {payments.summary()}")
                lines.append(f"            e.g. {self.reason_examples[key]}")
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
        # Column widths so payment log lines line up
        thread_width = len(str(self.options.threads - 1))
        name_width = max(len(ln.name) for ln in lns)
        impl_width = max(len(ln.impl) for ln in lns)
        amount_width = len(str(self.options.max_amount))
        count = 0
        while self.options.payments == 0 or count < self.options.payments:
            count += 1
            src, tgt = sample(lns, 2)
            amount = randint(self.options.min_amount, self.options.max_amount)
            # CLN requires invoice labels to be unique
            label = f"ln_activity-{thread_id}-{count}-{secrets.token_hex(4)}"
            start = time()
            hops = None
            try:
                invoice = tgt.createinvoice(amount, label)
            except Exception as e:
                succeeded, reason = False, f"createinvoice failed: {e}"
            else:
                try:
                    # Waits until the payment succeeded or failed
                    succeeded, reason, hops = src.pay(invoice)
                except Exception as e:
                    succeeded, reason = False, f"pay failed: {e}"
            seconds = time() - start
            self.stats.record(src, tgt, amount, succeeded, reason, hops, seconds)
            self.log.info(
                f"thread {thread_id:>{thread_width}}  "
                f"{src.name:<{name_width}} {src.impl:<{impl_width}} -> "
                f"{tgt.name:<{name_width}} {tgt.impl:<{impl_width}}  "
                f"{amount:>{amount_width}} sats  {'?' if hops is None else hops:>2} hops  "
                f"{'ok' if succeeded else 'FAILED':<6} {seconds:>5.1f}s"
                + ("" if succeeded else f"  {reason}")
            )
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

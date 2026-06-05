import argparse
import sys
import unittest


class TeeStream:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, text):
        for stream in self.streams:
            stream.write(text)
        return len(text)

    def writeln(self, text=''):
        self.write(text + '\n')

    def flush(self):
        for stream in self.streams:
            flush = getattr(stream, 'flush', None)
            if callable(flush):
                flush()


DEFAULT_START_DIR = 'test'
DEFAULT_PATTERN = 'test_*.py'
DEFAULT_TOP_LEVEL_DIR = '.'


class RollTextTestResult(unittest.TextTestResult):
    def __init__(self, stream, descriptions, verbosity, statusLines=False):
        super().__init__(stream, descriptions, verbosity)
        self.statusLines = bool(statusLines)

    @staticmethod
    def _testId(test):
        testId = getattr(test, 'id', None)
        return testId() if callable(testId) else str(test)

    def _writeStatus(self, status, test):
        if self.statusLines:
            self.stream.writeln(f'{status} {self._testId(test)}')

    def addSuccess(self, test):
        super().addSuccess(test)
        self._writeStatus('PASS', test)

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self._writeStatus('FAIL', test)

    def addError(self, test, err):
        super().addError(test, err)
        self._writeStatus('ERROR', test)

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self._writeStatus('SKIP', test)

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self._writeStatus('XFAIL', test)

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self._writeStatus('XPASS', test)


def parseArgs(argv):
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument('--report')
    parser.add_argument('--status-lines', action='store_true')
    parser.add_argument('-f', '--failfast', action='store_true')
    parser.add_argument('-b', '--buffer', action='store_true')
    parser.add_argument('-c', '--catch', dest='catchbreak', action='store_true')
    parser.add_argument('-q', '--quiet', action='store_true')
    parser.add_argument('-v', '--verbose', action='store_true')
    parser.add_argument('targets', nargs='*')
    args, extraArgs = parser.parse_known_args(argv)
    args.targets.extend(extraArgs)
    return args


def buildSuite(targets):
    loader = unittest.defaultTestLoader

    if not targets:
        return loader.discover(
            start_dir=DEFAULT_START_DIR,
            pattern=DEFAULT_PATTERN,
            top_level_dir=DEFAULT_TOP_LEVEL_DIR,
        )

    if targets[0] == 'discover':
        discoverParser = argparse.ArgumentParser(add_help=False)
        discoverParser.add_argument('-s', '--start-directory', default=DEFAULT_START_DIR)
        discoverParser.add_argument('-p', '--pattern', default=DEFAULT_PATTERN)
        discoverParser.add_argument('-t', '--top-level-directory', default=DEFAULT_TOP_LEVEL_DIR)
        discoverArgs, extraArgs = discoverParser.parse_known_args(targets[1:])
        if extraArgs:
            raise SystemExit(f'Unrecognized discover arguments: {" ".join(extraArgs)}')

        return loader.discover(
            start_dir=discoverArgs.start_directory,
            pattern=discoverArgs.pattern,
            top_level_dir=discoverArgs.top_level_directory,
        )

    return loader.loadTestsFromNames(targets)


def getVerbosity(args):
    if args.quiet:
        return 1
    if args.verbose:
        return 2
    return 2


def printProblemList(label, entries, stream):
    if not entries:
        return

    print(f'{label} ({len(entries)}):', file=stream)
    for testCase, _ in entries:
        testId = getattr(testCase, 'id', None)
        print(f' - {testId() if callable(testId) else testCase}', file=stream)


def printSummary(result, stream):
    print(file=stream)
    print('ROLL TEST SUMMARY', file=stream)
    print(f'Ran: {result.testsRun}', file=stream)
    print(f'Failures: {len(result.failures)}', file=stream)
    print(f'Errors: {len(result.errors)}', file=stream)
    print(f'Skipped: {len(result.skipped)}', file=stream)
    print(f'Expected failures: {len(result.expectedFailures)}', file=stream)
    print(f'Unexpected successes: {len(result.unexpectedSuccesses)}', file=stream)
    print(f'Status: {"PASS" if result.wasSuccessful() else "FAIL"}', file=stream)

    printProblemList('Errors', result.errors, stream)
    printProblemList('Failures', result.failures, stream)
    printProblemList('Unexpected successes', [(testCase, '') for testCase in result.unexpectedSuccesses], stream)


def buildStream(reportPath):
    if not reportPath:
        return sys.stdout, None

    reportHandle = open(reportPath, 'w', encoding='utf-8', newline='\n')
    return TeeStream(sys.stdout, reportHandle), reportHandle


def main(argv=None):
    args = parseArgs(argv or sys.argv[1:])
    emitStatusLines = args.status_lines or not args.targets
    suite = buildSuite(args.targets)
    stream, reportHandle = buildStream(args.report)

    def resultClass(streamArg, descriptionsArg, verbosityArg):
        return RollTextTestResult(streamArg, descriptionsArg, verbosityArg, statusLines=emitStatusLines)

    runner = unittest.TextTestRunner(
        stream=stream,
        verbosity=0 if emitStatusLines else getVerbosity(args),
        failfast=args.failfast,
        buffer=args.buffer,
        resultclass=resultClass,
    )

    if args.catchbreak:
        unittest.installHandler()

    try:
        result = runner.run(suite)
        printSummary(result, stream)
        stream.flush()
        return 0 if result.wasSuccessful() else 1
    finally:
        if reportHandle is not None:
            reportHandle.close()


if __name__ == '__main__':
    raise SystemExit(main())

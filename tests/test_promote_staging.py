import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]


class PromoteStaging(unittest.TestCase):
    def test_promotion_checks_every_commit_and_updates_both_remotes_without_force(self):
        script = (BASE / 'bin/promote-staging').read_text()
        self.assertIn('"$current_branch" != staging', script)
        self.assertIn('git rev-list --reverse "$main_sha..$staging_sha"', script)
        self.assertIn('verify-commit "$commit_sha"', script)
        self.assertIn('git push fleet staging:staging', script)
        self.assertIn('git push origin staging:staging', script)
        self.assertIn('git push fleet staging:main', script)
        self.assertIn('git push origin staging:main', script)
        self.assertIn('VM_MINT_PULL_STATUS_FILE', script)
        self.assertIn('VM_MINT_B_PULL_STATUS_FILE', script)
        self.assertIn('if (( push )) && [[ -z "$status_path" ]]', script)
        self.assertNotIn('--force', script)

    def test_only_exact_listed_unsigned_historic_commits_are_skipped(self):
        script = (BASE / 'bin/promote-staging').read_text()
        self.assertIn('files/unsigned_history_exceptions', script)
        self.assertIn('grep -Eq "^${commit_sha}( |$)"', script)
        exceptions = (BASE / 'files/unsigned_history_exceptions').read_text().splitlines()
        entries = [line.split()[0] for line in exceptions if line and not line.startswith('#')]
        self.assertEqual(entries, ['2e46064d43828c9612e6d91382c67a5ab718bd90'])


if __name__ == '__main__':
    unittest.main()

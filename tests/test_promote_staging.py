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


if __name__ == '__main__':
    unittest.main()

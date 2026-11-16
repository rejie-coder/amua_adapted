"""Provider regressions with explicit replacements for POSIX-specific OS tests."""
from pathlib import Path
import os,runpy,sys,unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'src/provider'),str(ROOT/'src'),str(ROOT/'tests/provider'),str(ROOT/'Amua/Resources')]
# These tests require POSIX executable scripts/flock mode bits. Native Windows jobs,
# cross-process byte locks and screenshot ACLs are tested independently on Windows.
replacements={
 'test_hardening.HardeningTests.test_crashed_writer_residue_recovers_live_lock_rejects':'Windows native cross-process lock test',
 'test_hardening.HardeningTests.test_stop_reaps_descendant_and_removes_snapshot':'Windows native kill-on-close job and packaged engine test',
 'test_hardening.HardeningTests.test_engine_output_budget_stops_oversized_child':'Windows native owned process test; source bound preserved',
 'test_review_cache.ReviewCacheTests.test_cache_permissions_no_prompt_history_or_credentials':'Windows Credential Manager and native screenshot ACL checks',
}
loader=unittest.TestLoader();suite=loader.discover(str(ROOT/'tests/provider'))
def walk(items):
 for item in items:
  if isinstance(item,unittest.TestSuite):yield from walk(item)
  else:yield item
for test in walk(suite):
 reason=replacements.get(test.id())
 if reason:
  def skip(self,reason=reason):self.skipTest('POSIX-specific test replaced by '+reason)
  setattr(test,test._testMethodName,skip.__get__(test,type(test)))
result=unittest.TextTestRunner(verbosity=2).run(suite);raise SystemExit(0 if result.wasSuccessful() else 1)

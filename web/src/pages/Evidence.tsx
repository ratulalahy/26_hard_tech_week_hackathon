// The Evidence page (T21): the method and evidence content as a page of its own, beside the Story page's
// drawer. It reads the window the top bar's year switch selects: the assumptions register, the policy table,
// the checks and limitations for either year; the validation → test drift and the test-year extras only
// when the sealed test year is selected (they exist only in results/test).
import { useCopy } from '../lib/useCopy';
import { useApp } from '../lib/store';
import { MethodBody, runLine } from '../views/MethodDrawer';

export function Evidence() {
  const { data, evalWindow, testIndex, set } = useApp();
  const copy = useCopy();
  const man = data!.manifest;
  const testOn = !!testIndex?.available;
  return (
    <section aria-label="Method and evidence" data-testid="evidence" tabIndex={0} className="page-scroll">
      <div className="evidence-col flex flex-col gap-4">
        <header>
          <h1 className="t-20" style={{ margin: 0 }} data-testid="evidence-title">Method and evidence: what each number is, and what it is not</h1>
          <p className="t-12 ink-2" style={{ margin: '4px 0 0' }}>{runLine(copy, man)}</p>
          {evalWindow === 'validation' ? (
            <p className="t-12 ink-2" style={{ margin: '8px 0 0' }} data-testid="evidence-drift-hint">
              The validation → test drift table and the test year's pre-registered extras come from the sealed test year's files{testOn ? '' : ', which are not in this build'}.
              {testOn ? <> <button className="btn" style={{ height: 28, marginLeft: 4 }} onClick={() => set({ evalWindow: 'test' })}>Show the test year</button></> : null}
            </p>
          ) : null}
        </header>
        <div className="panel flex flex-col gap-4">
          <MethodBody />
        </div>
      </div>
    </section>
  );
}

"""Real desktop/mobile commerce UI against application-only development processes."""
import os
import subprocess
import commerce_flow as flow
apps=flow.local.Applications()
try:
    apps.start()
    flow.local.request(apps.urls['identity'],'/internal/identity/operators',{'email':'operator@example.test','password':'ApplicationTestsOnly123!'})
    env=dict(os.environ,FULL_COMMERCE='1')
    subprocess.run(['npm','run','test:browser','--','--grep','complete commerce UI','--workers=1'],cwd=flow.ROOT/'frontend',env=env,check=True)
finally:apps.close()

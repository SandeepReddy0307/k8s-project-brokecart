#!/usr/bin/env python3
"""Application-only development launcher. Does not create infrastructure or Docker containers."""
import argparse
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
NAMES = ['catalog','pricing','identity','cart','checkout','orders','inventory','payments','payment-provider','shipping','returns','notifications','search','reporting']
PORTS = {name: 8081 + i for i,name in enumerate(NAMES)}
TOPICS = {
    'catalog.events':['search'], 'inventory.commands':['inventory'], 'inventory.events':['orders'],
    'payments.commands':['payments'], 'payments.events':['orders','returns'],
    'shipping.commands':['shipping'], 'shipping.events':['orders','notifications'],
    'orders.events':['inventory','notifications','reporting'], 'returns.events':['orders','notifications'],
}
TOKEN = 'brokecart-local-internal-token-only-for-development'

def request(base,path,body=None,timeout=20):
    data=None if body is None else json.dumps(body).encode()
    req=urllib.request.Request(base+path,data=data,headers={'Content-Type':'application/json','X-Internal-Token':TOKEN})
    with urllib.request.urlopen(req,timeout=timeout) as response:
        raw=response.read()
        return json.loads(raw) if raw else {}

class Relay:
    def __init__(self,urls): self.urls=urls;self.stop=threading.Event();self.failures=[]
    def tick(self):
        for name in NAMES:
            for record in request(self.urls[name],'/internal/outbox'):
                for target in TOPICS.get(record['topic'],[]):
                    request(self.urls[target],'/internal/events',record['event'])
                request(self.urls[name],'/internal/outbox/'+record['eventId']+'/ack',{})
    def run(self):
        while not self.stop.is_set():
            try:self.tick()
            except Exception as error:self.failures.append(str(error));self.failures=self.failures[-20:]
            self.stop.wait(.25)

class Applications:
    def __init__(self,port_offset=0,environment=None):
        self.urls={name:f'http://127.0.0.1:{port+port_offset}' for name,port in PORTS.items()}
        self.environment=environment or {};self.processes=[];self.logs=Path(tempfile.mkdtemp(prefix='brokecart-apps-'));self.relay=None;self.runtime=tempfile.TemporaryDirectory(prefix='brokecart-runtime-')
    def start(self,relay=True):
        peers={name.upper().replace('-','_')+'_URL':url for name,url in self.urls.items()}
        for index,name in enumerate(NAMES):
            jar=ROOT/f'services/{name}-service/target/{name}-service-0.1.0-SNAPSHOT.jar'
            if not jar.exists():raise RuntimeError('Build application JARs first: ./mvnw package')
            runtime_jar=Path(self.runtime.name)/(name+'.jar');shutil.copyfile(jar,runtime_jar)
            env=dict(os.environ);env.update(SPRING_PROFILES_ACTIVE='local',KAFKA_ENABLED='false',REDIS_ENABLED='false',PUBLIC_ORIGIN='http://localhost:5173',CATALOG_BASE_URL=self.urls['catalog'],**peers);env.update(self.environment(name) if callable(self.environment) else self.environment)
            log=open(self.logs/(name+'.log'),'w')
            process=subprocess.Popen(['java','-Xmx160m','-XX:ActiveProcessorCount=2','-jar',str(runtime_jar),'--server.address=127.0.0.1','--server.port='+self.urls[name].rsplit(':',1)[1]],env=env,stdout=log,stderr=subprocess.STDOUT)
            self.processes.append(process)
            if index % 3 == 2 or index == len(NAMES)-1:
                for pending in NAMES[(index//3)*3:index+1]:
                    self.wait_ready(pending)
                print('Ready: '+', '.join(NAMES[(index//3)*3:index+1]),flush=True)
        if relay:
            self.relay=Relay(self.urls);threading.Thread(target=self.relay.run,daemon=True).start()
        return self
    def wait_ready(self,name):
        deadline=time.monotonic()+240
        while time.monotonic()<deadline:
            if any(p.poll() is not None for p in self.processes):raise RuntimeError(f'Application exited; inspect {self.logs}')
            try:request(self.urls[name],'/actuator/health/readiness',timeout=2);return
            except Exception:time.sleep(.5)
        raise RuntimeError(f'{name} did not become ready; inspect {self.logs}')
    def close(self):
        if self.relay:self.relay.stop.set()
        for p in self.processes:
            if p.poll() is None:p.terminate()
        for p in self.processes:
            try:p.wait(timeout=10)
            except subprocess.TimeoutExpired:p.kill();p.wait()
        self.runtime.cleanup()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--port-offset',type=int,default=0);args=parser.parse_args()
    apps=Applications(args.port_offset)
    try:
        apps.start();print('BrokeCart development applications ready. Logs:',apps.logs,flush=True)
        password=os.environ.get('BROKECART_OPERATOR_PASSWORD')
        if password:
            request(apps.urls['identity'],'/internal/identity/operators',{'email':'operator@brokecart.local','password':password})
            print('Operator account: operator@brokecart.local (password from BROKECART_OPERATOR_PASSWORD)',flush=True)
        print('Run npm run dev in frontend/ and open http://localhost:5173',flush=True)
        print('Development mode uses H2/local cart storage and an HTTP event relay, not Kafka/Redis.',flush=True)
        while True:time.sleep(1)
    except KeyboardInterrupt:pass
    finally:apps.close()

import subprocess, queue, threading, time, sys, json
J="/root/.gradle/jdks/eclipse_adoptium-17-amd64-linux/jdk-17.0.21+9/bin/java"
TAG=sys.argv[1]
args=[J,"-Xmx5G",f"-XX:StartFlightRecording=filename=/home/claude/srv/{TAG}.jfr,settings=profile,dumponexit=true","@libraries/net/minecraftforge/forge/1.20.1-47.4.10/unix_args.txt","nogui"]
p=subprocess.Popen(args,cwd="/home/claude/srv",stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
q=queue.Queue(); log=open(f"/home/claude/srv/{TAG}.log","w")
def lire():
    for l in p.stdout: log.write(l); log.flush(); q.put(l)
    q.put(None)
threading.Thread(target=lire,daemon=True).start()
def vider():
    out=[]
    while True:
        try: out.append(q.get_nowait())
        except queue.Empty: return out
def att(m,d):
    f=time.time()+d
    while time.time()<f:
        try: l=q.get(timeout=5)
        except queue.Empty: continue
        if l is None: sys.exit("arret")
        if m in l: return l
    sys.exit("delai "+m)
def cmd(c): log.write(">>> "+c+"\n"); p.stdin.write(c+"\n"); p.stdin.flush()
t0=time.time(); att("Done (",1500); print("pret", round(time.time()-t0), flush=True)
B=445.28; R=6
Z={"paris":(2.35,48.85),"alpes":(7.0,45.9),"atlantique":(-25,45),"sahara":(10,24),"nil":(32.9,24),"serengeti":(34.8,-2.5)}
res={}
for nom,(lon,lat) in Z.items():
    cx,cz=int(lon*B)>>4,int(-lat*B)>>4
    vider(); t=time.time()
    cmd(f"forceload add {(cx-R)*16} {(cz-R)*16} {(cx+R)*16+15} {(cz+R)*16+15}")
    # attendre que les 4 coins soient chargés
    ok=False
    while time.time()-t<1200:
        time.sleep(3); vider()
        cmd(f"execute if loaded {(cx-R)*16} 64 {(cz-R)*16} if loaded {(cx+R)*16} 64 {(cz+R)*16} if loaded {(cx-R)*16} 64 {(cz+R)*16} if loaded {(cx+R)*16} 64 {(cz-R)*16} run say PRET_{nom}")
        f=time.time()+4
        while time.time()<f:
            try: l=q.get(timeout=1)
            except queue.Empty: continue
            if l and f"PRET_{nom}" in l: ok=True; break
        if ok: break
    dt=time.time()-t; n=(2*R+1)**2
    res[nom]=(round(dt,1), n, round(n/dt,2)); print(nom,res[nom],flush=True)
    cmd("forceload remove all"); time.sleep(5)
cmd("save-all flush"); att("Saved the game",600)
cmd("stop"); p.wait(timeout=600)
json.dump(res,open(f"/home/claude/srv/{TAG}.json","w")); print("fini",res)

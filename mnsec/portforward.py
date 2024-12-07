"""PortForward based on socat."""

import subprocess
import contextlib
import atexit

def portforward(port1=None, host2=None, port2=None, proto="tcp", host1="0.0.0.0", proto2=None):
    if not port1 or not host2 or not port2:
        raise ValueError(f"Invalid mandatory fields: port1={port1} host2={host2} port2={port2}")

    proto2 = proto if proto2 is None else proto2
    command = ['socat', '-lpmnsec-socat-%s-%s-%s-%s' % (proto, port1, host2, port2),
               '%s-listen:%s,bind=%s,reuseaddr,fork' % (proto, port1, host1),
               '%s:%s:%s' % (proto2, host2, port2)]
    kwargs = {'stdin': subprocess.DEVNULL, 'stdout': subprocess.DEVNULL,
              'stderr': subprocess.PIPE}
    proc = subprocess.Popen(command, **kwargs)

    with contextlib.suppress(subprocess.TimeoutExpired):
        proc.wait(timeout=0.0)
        outs, errs = proc.communicate()
        raise Exception(f"Failed to start portforward on port {port1}: PID {proc.pid} died (RC={proc.returncode} error={errs}) (cmd={command})" )
    return proc


@atexit.register
def _cleanup_all():
    with contextlib.suppress(Exception):
        subprocess.run(["/usr/bin/pkill", "-f", "socat -lpmnsec-socat"])

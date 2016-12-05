import select
import subprocess
import time

def wait_for_start_line(cmd, confirmed_line, watch='stdout', timeout=5):
    if isinstance(confirmed_line, str):
        confirmed_line = confirmed_line.encode('utf-8')
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    pipe = getattr(process, watch)
    # wait until we get the "server started" message, otherwise tests
    # may fail due to redis not having actually started yet
    start_time = time.time()
    if hasattr(select, 'epoll'):
        poll = select.epoll()
        poll.register(pipe, select.POLLIN)
        while time.time() - timeout < start_time:
            if poll.poll(0):
                line = pipe.readline()
                if confirmed_line in line:
                    poll.unregister(pipe)
                    return process
        poll.unregister(pipe)
    elif hasattr(select, 'kqueue'):
        kq = select.kqueue()
        kq.control([select.kevent(pipe, select.KQ_FILTER_READ, select.KQ_EV_ENABLE | select.KQ_EV_ADD)], 0, 0)
        while time.time() - timeout < start_time:
            if kq.control(None, 1, 1.):
                line = pipe.readline()
                if confirmed_line in line:
                    kq.close()
                    return process
        kq.close()
    else:
        process.terminate()
        raise Exception("No polling available")
    process.terminate()
    raise Exception("process took too long to start...")

def shutdown_process(process):
    process.terminate()
    # wait until the process terminates before continuing
    process.wait()
    # check if there's something else to do after terminate
    if hasattr(process, '_post_terminate_cleanup') and process._post_terminate_cleanup is not None:
        process._post_terminate_cleanup()

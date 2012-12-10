import sys
import time
import os
import shlex, subprocess
from datetime import datetime
from django.shortcuts import render_to_response, RequestContext, redirect
from settings import SERVER_NAME

def get_w():
    result = {}
    command = 'w'
    out, err = subprocess.Popen(shlex.split(command), stdout=subprocess.PIPE).communicate()
    splitted = out.split('\n')
    header = splitted[0]
    result['load averages'] = [x.strip() for x in header[header.index('load average:') + len('lead average:'):].split(',')]
    header = header[:header.index('load') - 3]
    result['users'] = header.split(',')[-1].strip()
    header = header[:header.index(result['users'])].strip()
    result['time'] = header[:8]
    result['uptime'] = header.replace(result['time'], '').strip()[:-1]
    result['user_list'] = {}
    result['user_list']['headers'] = splitted[1].split()
    result['user_list']['values'] = []
    splitted = splitted[2:]
    for line in splitted:
        values = line.split()
        if len(values) > 7:
            for i in range(8, len(values)):
                values += values[i]
            values = values[:8]
        result['user_list']['values'].append(values) 

    return result

def get_mem_info():
    result = {}
    command = 'free -m'
    out, err = subprocess.Popen(shlex.split(command), stdout=subprocess.PIPE).communicate()
    values = out.split()
    for i, v in enumerate(values):
        if i < 6:
            result[v] = values[i + 7]
    return result

def search_process(list, upstream):
    for line in list.split('\n'):
        if line.find(':%s' % upstream.split(':')[-1]) != -1:
            return ' '.join(line.split()).split(' ')[-1]
    return ''

def index(request):
    import os
    os.chdir('/etc/nginx/sites-enabled')
    files = os.listdir('.')
    sites = []
    upstreams = []
    for file in files:
       content = open(file).read()
       server_name = ''
       upstream = {}
       upstream_name = ''
       fastcgi = False
       got_upstream_node = False
       for line in content.split('\n'):
           if got_upstream_node and line.strip().startswith('server'):
               upstream['uri'] = ' '.join(line.split()).lstrip().split(' ')[1][:-1]
               upstreams.append(upstream)
           if line.strip().startswith('server_name'):
               server_name = ' '.join(line.split()).lstrip().split(' ')[1][:-1]
           if line.strip().startswith('upstream'):
               got_upstream_node = True
	       upstream['name'] = ' '.join(line.split()).lstrip().split(' ')[1]
               upstream_name = upstream['name']
           else:
               got_upstream_node = False
           if line.strip().startswith('fastcgi_pass'):
               fastcgi = True
               upstream_name = ' '.join(line.split()).lstrip().split(' ')[1][:-1]
       sites.append({
           'server_name' : server_name,
           'upstream'    : upstream,
           'upstream_name' : upstream_name,
           'fastcgi' : 'Yes' if fastcgi else 'No'
       })
    sites = [s for s in sites if s['server_name'] != 'localhost']
    command = 'netstat -tulpn'
    out, err = subprocess.Popen(shlex.split(command), stdout=subprocess.PIPE).communicate()
    for site in sites:
        _upstreams = filter(lambda u: u['name'] == site['upstream_name'], upstreams)
        if len(_upstreams):
           site['upstream_name'] = _upstreams[0]['name']
           site['upstream_uri'] = _upstreams[0]['uri']
           site['process'] = search_process(out, site['upstream_uri'])
           site['pid'] = site['process'].split('/')[0] if site['process'].find('python') != -1 else None
        else:
           site['upstream_name'] = ''
           site['upstream_uri'] = ''
           #site['process'] = '-'
    return render_to_response('index.html', {'server_name' : SERVER_NAME, 'w' : get_w(), 'mem_info' : get_mem_info() ,'sites' : sites, 'timestamp' : datetime.now().strftime("%A %d, %B %Y on %I:%M %p"), 'python_version' : sys.version })      


def restart_process(request):
    if request.method == 'POST':
        pid = request.POST['pid']
        command = 'lsof'
        out, err = subprocess.Popen(shlex.split(command), stdout=subprocess.PIPE).communicate()
        lines = [l.split() for l in out.split('\n')]
        lines = [l  for l in lines if len(l) > 0]
        lines = [l for l in lines if l[1] == pid]
        line = [l for l in lines if l[3] == 'txt'][0]
        if line[0].find('gunicorn') > -1:
            cwd = line[-1].replace('/env/bin/python', '')
            gunicorn_path = cwd
            conf_path = cwd
            app_path = cwd
            
            def search_file(filename, root, exclude=[]):
                result = None
                for cur, dirnames, filenames in os.walk(root):
                    if filename in filenames:
                        proceed = True
                        for d in exclude:
                            if cur.find(d) > -1:
                                proceed = False
                        if proceed:
                            result = cur
                            break
                return result

            print cwd

            gunicorn_path = search_file('gunicorn_django', gunicorn_path)
            conf_path = search_file('gunicorn.conf.py', conf_path)
            app_path = search_file('manage.py', app_path, ['site-packages'])
           
            command = 'kill %s' % pid
            out, err = subprocess.Popen(shlex.split(command), stdout=subprocess.PIPE).communicate()

            command = '%s/gunicorn_django -c %s/gunicorn.conf.py %s --daemon' % (gunicorn_path, conf_path, app_path)
            print command
            out, err = subprocess.Popen(shlex.split(command), stdout=subprocess.PIPE).communicate()
           
            time.sleep(2)
            return redirect('/')

import sys
import shlex, subprocess
from datetime import datetime
from django.shortcuts import render_to_response, RequestContext

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
        else:
           site['upstream_name'] = ''
           site['upstream_uri'] = ''
           #site['process'] = '-'
    return render_to_response('index.html', { 'mem_info' : get_mem_info() ,'sites' : sites, 'timestamp' : datetime.now().strftime("%A %d, %B %Y on %I:%M %p"), 'python_version' : sys.version })      

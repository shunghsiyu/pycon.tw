# -*- coding: utf-8 -*-

import functools
import os
import sys

from fabric.api import cd, lcd, local, run, settings, sudo
from fabric.api import task
from fabric.api import env

env.forward_agent = True


PROJECT_DIR = os.environ.get('PROJECT_DIR', '')
PROJECT_NAME = os.environ.get('PROJECT_NAME', '')
DJANGO_DIR = PROJECT_DIR + '/' + PROJECT_NAME

VIRTUALENV_NAME = os.environ.get('VIRTUALENV_NAME', '')
SUPERVISOR_NAME = os.environ.get('SUPERVISOR_NAME', '')


def upgrade_system():
    sudo('apt-get update -y')


def install_requirements():
    with cd(PROJECT_DIR):
        run('~/.virtualenvs/{0}/bin/pip install -r requirements/production.txt'.format(VIRTUALENV_NAME))


def migrate_db():
    with cd(DJANGO_DIR):
        run('source {0}/env.sh && ~/.virtualenvs/{1}/bin/python manage.py migrate'.format(PROJECT_DIR, VIRTUALENV_NAME))


def pull_repo():
    with cd(PROJECT_DIR):
        run('git pull origin master')


def restart_services():
    sudo('supervisorctl restart {0}'.format(SUPERVISOR_NAME))
    sudo('service nginx restart')


def collectstatic():
    with cd(DJANGO_DIR):
        run('source {0}/env.sh && ~/.virtualenvs/{1}/bin/python manage.py collectstatic --noinput -c'.format(PROJECT_DIR, VIRTUALENV_NAME))


def compile_translations():
    with cd(DJANGO_DIR):
        # run('~/.virtualenvs/{0}/bin/tx pull'.format(VIRTUALENV_NAME))
        run('~/.virtualenvs/{0}/bin/python manage.py compilemessages'.format(
            VIRTUALENV_NAME,
        ))


@task
def deploy():
    pull_repo()
    install_requirements()
    collectstatic()
    migrate_db()
    compile_translations()
    restart_services()


@task
def pull_transifex():
    with lcd('src'):
        local('tx pull')
        local('python manage.py compilemessages')


@task
def push_transifex(source=True, translation=True):
    with lcd('src'):
        local('python manage.py makemessages -a')

        push_cmd_parts = ['tx', 'push']
        if source:
            push_cmd_parts.append('-s')
        if translation:
            push_cmd_parts.append('-t')
        local(' '.join(push_cmd_parts))


##############################
# Scripts used on Travis CI. #
##############################


def setup_transifex(func):

    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        transifexrc_path = os.path.expanduser('~/.transifexrc')
        if not os.path.exists(transifexrc_path):
            with open(transifexrc_path, 'w') as f:
                f.write((
                    '[https://www.transifex.com]\n'
                    'hostname = https://www.transifex.com\n'
                    'password = {password}\n'
                    'token = \n'
                    'username = pycontw\n'
                ).format(password=os.environ['TRANSIFEX_PASSWORD']))
        func(*args, **kwargs)

    return wrapped


def setup_git(func):

    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        local('git config user.name "Travis CI"')
        local('git config user.email "travis-ci@pycon.tw"')

        netrc_path = os.path.expanduser('~/.netrc')
        if not os.path.exists(netrc_path):
            with open(netrc_path, 'w') as f:
                f.write(
                    ('machine github.com\n'
                     '    login {user}\n'
                     '    password {password}\n').format(
                        user=os.environ['GITHUB_USERNAME'],
                        password=os.environ['GITHUB_PASSWORD'],
                    ),
                )
        func(*args, **kwargs)

    return wrapped


def restrict_branch(branch, *, no_pr=True):

    def _restrict_branch_inner(f):

        @functools.wraps(f)
        def wrapped(*args, **kwargs):
            current = os.getenv('TRAVIS_BRANCH')
            if current != branch:
                print('Branch {cur} is not {target}. '
                      'Job {jname} skipped.'.format(
                          cur=current, target=branch, jname=f.__name__),
                      file=sys.stderr)
                return
            if no_pr and os.getenv('TRAVIS_PULL_REQUEST') != 'false':
                print('Build triggered by a pull request. '
                      'Job {} skipped.'.format(f.__name__), file=sys.stderr)
                return
            f(*args, **kwargs)

        return wrapped

    return _restrict_branch_inner


@task
@restrict_branch('master')
@setup_transifex
def travis_push_transifex():
    push_transifex(translation=False)


@task
@restrict_branch('travis-tx-commit')
@setup_transifex
@setup_git
def travis_pull_transifex():
    pull_transifex()
    local('git add src/locale/')
    with settings(warn_only=True):
        r = local('git commit -m "Update translations [skip travis]"')
    if r.failed:    # Most likely because of an empty commit.
        print(r, file=sys.stderr)
        return

    r = local('git remote 2>/dev/null | head -n1', capture=True).strip()

    # Ignore failed push since we can always wait for another build,
    # or just pull translations manually.
    with settings(warn_only=True):
        local('git push {remote} {branch}'.format(
            remote=str(r), branch=os.environ['TRAVIS_BRANCH'],
        ))

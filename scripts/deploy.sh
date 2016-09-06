#! /usr/bin/env bash

# avaliable apps
allapps=($(ls -l /app/deploy/apps | egrep '^d' | cut -c 46-55 | tr '\n' ' '))
consumers=($(grep 'program:consumer' /etc/supervisord.conf | cut -c 10-19 |  tr '\n' ' '))
use=$(ls -l /app/deploy/apps | egrep '^d' | cut -c 46-55 | tr '\n' ' ')

# check num of param
if [ $# == 0 ]; then
  echo "Useage: deploy.sh all"
  echo "    or: deploy.sh [$use] ..."
  echo "        (support multiple apps deployment simultaneously)"
  exit 1
fi

# check if has "all"
if `echo $@ | grep -q "all"`; then
  # more than one "all"
  if [ $# -gt 1 ]; then
    echo " ERROR: invalid params! "
    echo "Useage: deploy.sh all"
    echo "    or: deploy.sh [$use] ..."
    echo "        (support multiple apps deployment simultaneously)"
    exit 1
  else
    apps=("${allapps[@]}")
  fi
else
  apps=( "$@" )
fi

# check app name
for app in "${apps[@]}"; do
  if [ ! -d /app/deploy/apps/${app} ]; then
    echo " ERROR: invalid app name: ${app}"
    echo "Useage: deploy.sh all"
    echo "    or: deploy.sh [$use] ..."
    echo "        (support multiple apps deployment simultaneously)"
    exit 1
  fi
done

# deploy apps
echo "start deploy $@" >> /root/deploy-log.txt
date >> /root/deploy-log.txt
for app in "${apps[@]}"; do
  # deploy other app
  if [ ${app} == 'consumers' ]; then
    # deploy consumers
    echo "------deploy consumers------"
    su - deploy <<CODE
    cd /app/deploy/apps/${app}
    git reset --hard HEAD
    git checkout develop
    git fetch origin
    git rebase origin/develop
    git rev-parse HEAD >> /app/deploy/deploy-log.txt
    # install requirements
    /app/deploy/venv/bin/pip install -q -r requirements.txt
CODE
    # deploy every consumer
    for app in "${consumers[@]}"; do
      echo "------Deploy ${app}------"
      # stop program
      supervisorctl stop "${app}:*"
      # start program
      supervisorctl start "${app}:*"
      echo "------Deploy ${app} Finish------"
      echo
    done
  elif [ ${app} == 'jobs' ]; then
    # deploy jobs
    echo "------deploy jobs ------"
    su - deploy <<CODE
    cd /app/deploy/apps/${app}
    git reset --hard HEAD
    git checkout develop
    git fetch origin
    git rebase origin/develop
    git rev-parse HEAD >> /app/deploy/deploy-log.txt
    # install requirements
    /app/deploy/venv/bin/pip install -q -r requirements.txt
CODE
    echo "------Deploy ${app} Finish------"
    echo
  else
    echo "------Deploy ${app}------"
    # stop program
    supervisorctl stop "${app}:*"
    # get lastest code
    su - deploy <<CODE
    cd /app/deploy/apps/${app}
    git reset --hard HEAD
    git checkout develop
    git fetch origin
    git rebase origin/develop
    git rev-parse HEAD >> /app/deploy/deploy-log.txt
    # install requirements
    /app/deploy/venv/bin/pip install -q -r requirements.txt
CODE
    # start program
    supervisorctl start "${app}:*"
    echo "------Deploy ${app} Finish------"
    echo
  fi
done
echo "------------Finish!" >> /root/deploy-log.txt
echo "Deploy Finish!"

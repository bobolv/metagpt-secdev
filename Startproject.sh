# #!/bin/bash

# PROJECT=$1
# STAGE=$2

# if [ -z "$PROJECT" ]; then
#   echo "Usage: ./run.sh <project_name> <stage>"
#   exit 1
# fi

# PROJECT_PATH="./projects/$PROJECT"

# echo "=== MetaGPT Lifecycle System ==="
# echo "Project: $PROJECT"
# echo "Stage: $STAGE"

# case $STAGE in
#   init)
#     echo "Initializing project lifecycle..."
#     mkdir -p $PROJECT_PATH
#     cp templates/* $PROJECT_PATH/ 2>/dev/null
#     ;;

#   requirement)
#     echo "Generating requirement document..."
#     docker exec metagpt-dev python tools/lifecycle_agent.py requirement $PROJECT
#     ;;

#   design)
#     echo "Generating design document..."
#     docker exec metagpt-dev python tools/lifecycle_agent.py design $PROJECT
#     ;;

#   implement)
#     echo "Generating implementation plan..."
#     docker exec metagpt-dev python tools/lifecycle_agent.py implementation $PROJECT
#     ;;

#   test)
#     echo "Generating test plan..."
#     docker exec metagpt-dev python tools/lifecycle_agent.py test $PROJECT
#     ;;

#   accept)
#     echo "Generating acceptance criteria..."
#     docker exec metagpt-dev python tools/lifecycle_agent.py acceptance $PROJECT
#     ;;

#   *)
#     echo "Unknown stage: $STAGE"
#     ;;
# esac


#!/bin/bash

PROJECT=$1
MODE=$2

if [ "$MODE" == "auto" ]; then
    echo "🚀 Auto lifecycle mode"
    python3 tools/lifecycle_orchestrator.py $PROJECT
    exit 0
fi

echo "Manual mode: $MODE"

python tools/lifecycle_agent.py $MODE $PROJECT
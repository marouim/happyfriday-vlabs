# Virtual Labs

Cette application est composee de deux workloads OpenShift independants :

| Application | Sources | Image S2I | Ressources exposees |
| --- | --- | --- | --- |
| Backend Flask | `backend/` | Python | `virtual-labs-backend` (`/api/*`) |
| Frontend Vue | `frontend/` | Node.js | `virtual-labs-frontend` |

Chaque dossier contient ses propres templates `openshift/template.yaml` et
`openshift/binary-template.yaml`. Les templates produisent deux
`BuildConfig`, deux `ImageStream`, deux `Deployment` et deux conteneurs
distincts.

## Build binaire local

Depuis la racine du projet :

```bash
oc login https://api.example.openshift.com:6443
oc project my-project

oc process -f backend/openshift/binary-template.yaml | oc apply -f -
oc start-build virtual-labs-backend --from-dir=backend --follow

BACKEND_URL=https://$(oc get route virtual-labs-backend -o jsonpath='{.spec.host}')
oc process -f frontend/openshift/binary-template.yaml \
  -p BACKEND_BASE_URL=${BACKEND_URL} \
  | oc apply -f -
oc start-build virtual-labs-frontend --from-dir=frontend --follow

oc get route virtual-labs-backend virtual-labs-frontend
```

## Build depuis un depot commun

```bash
REPOSITORY_URL=https://github.com/example/virtual-labs.git

oc process -f backend/openshift/template.yaml \
  -p SOURCE_REPOSITORY_URL=${REPOSITORY_URL} \
  -p SOURCE_REPOSITORY_REF=main \
  -p CONTEXT_DIR=backend \
  | oc apply -f -
oc start-build virtual-labs-backend --follow

BACKEND_URL=https://$(oc get route virtual-labs-backend -o jsonpath='{.spec.host}')
oc process -f frontend/openshift/template.yaml \
  -p SOURCE_REPOSITORY_URL=${REPOSITORY_URL} \
  -p SOURCE_REPOSITORY_REF=main \
  -p CONTEXT_DIR=frontend \
  -p BACKEND_BASE_URL=${BACKEND_URL} \
  | oc apply -f -
oc start-build virtual-labs-frontend --follow
```

L'URL du backend est integree au bundle Vue pendant son build. Si la route API
change, reconstruire l'image frontend.

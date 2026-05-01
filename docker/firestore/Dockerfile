FROM node:20-alpine

WORKDIR /emulator

RUN apk add --no-cache curl
RUN npm i -g firebase-tools@13.31.1

COPY docker/firestore/firebase.json /emulator/firebase.json
COPY docker/firestore/.firebaserc /emulator/.firebaserc

CMD ["firebase", "emulators:start", "--only", "firestore", "--project", "demo-project", "--host", "0.0.0.0", "--port", "8080"]

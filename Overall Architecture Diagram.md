## Overall Architecture DDiagram

### Schematic

![High level workflow](<Screenshot 2025-03-28 at 10.39.10 AM.png>)

### MermaidChart Code

````graph TB
User[User] -->|Creates flows<br>Views results| RapidPro

    subgraph "RapidPro Ecosystem"
        RapidPro[RapidPro<br>Web Application] -->|Triggers flow<br>executions| Mailroom
        RapidPro <-->|Reads/writes<br>data| Database[(PostgreSQL)]
        RapidPro -->|Queues<br>messages| Courier

        Mailroom[Mailroom<br>Flow Engine] <-->|Executes<br>flows| Database
        Mailroom -->|Logs<br>operations| DynamoDB[(DynamoDB)]
        Mailroom -->|Queues<br>outgoing msgs| Courier

        Courier[Courier<br>Channel Gateway] <-->|Reads/writes<br>messages| Database
        Courier <-->|Sends/receives<br>messages| Channels[Channel APIs<br>SMS, WhatsApp, etc.]

        Database -->|Archives<br>old data| Archiver[rp-archiver]
        Archiver -->|Stores<br>archives| S3[(S3/Cloud<br>Storage)]

        Database -->|Indexes<br>data| Indexer[rp-indexer]
        Indexer -->|Updates<br>indices| Elastic[(Elasticsearch)]
    end

Channels <-->|Messages| EndUsers[End Users<br>Phones/Apps]```
````

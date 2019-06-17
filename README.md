# RepeaterManager
MMDVMHost / HBlink DMR Repeater Management/Monitoring System

### NOTE: This is a *very* early prototype/work in progress! Do not expect everything to work. It's mostly public as a sneak-preview of where I'm headed with this new log aggregation protocol. 

#### Working as planned:
- mmdvmhost_logmon (proof-of-concept service to generate new "standard-protocol" logs)
- Fanout to browser clients using Server-sent events (SSE)
- MQTT-based log transport from repeaters to central server

#### Not Fully Implemented:
- Call Log / System Log Persistent Storage (60%)
- Web UI for viewing historical & streaming call statistics/system data (10%)

#### Not Started Yet:
- Websocket-based live call data to browsers (for ~browsers~ _Edge_ that don't support SSE)
- Raw TCP Log Transport


### Notes from some of my e-mails on the DVSwitch mailing list:

Maybe we can start to settle on a standard format for the new logging mechanism. The MMDVMHost monitoring utility I wrote last week monitors either a log file or the systemd journal (I'm using the journal for all our logs, no more plain files) and sends out state information. Here's what the format looks like right now:


When a server is started, just basic state info is reported:

`{"Status": "Idle"}`

As a voice or data transmission is started (either from RF or from Net), a payload is reported with basic call info:

`{"Status": "TX", "Origin": "Net", "CallType": "Group", "Destination": "31131", "Source": "N4NQV", "Mode": "Voice"}`


Then, at the end of the call, a new payload with additional info gets reported:

`{"Status": "Idle", "Origin": "Net", "Loss": "0%", "CallType": "Group", "Destination": "31131", "Source": "N4NQV", "Length": "4.5s", "Mode": "Voice", "BER": "0.0%"}`

The topic name has the repeater's ID, as well as the timeslot. If I was going to report this via TCP or UDP instead of MQTT, I'd probably structure it something like this instead:

```
{
310124: {
1: {"Status": "Idle", "Origin": "Net", "Loss": "0%", "CallType": "Group", "Destination": "31131", "Source": "N4NQV", "Length": "4.5s", "Mode": "Voice", "BER": "0.0%"},
2: {"Status": "Idle", "Origin": "Net", "Loss": "1%", "CallType": "Group", "Destination": "2", "Source": "KD4LZL", "Length": "4.4s", "Mode": "Voice", "BER": "0.0%"}
}
}
```

I envisioned a model where different repeater controller software, bridge software, etc could report log information in a format similar to this, using their choice of TCP, UDP, or MQTT. This is just a starting point though, there's definitely more information to be added (location, IPs, etc - the sky is the limit). I'm absolutely open to critique and suggestion, though. I definitely want this standard should be a collaborative effort between the people working with and generating the data. 

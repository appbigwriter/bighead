# Colaboracao

## Escopo

Cobertura de `T10-T13`: lista de salas, timeline conversacional, membros/privacidade e arquivos.

## Contratos necessarios

| Tela | Endpoint | Regra chave |
|---|---|---|
| T10 | `GET /v1/rooms` | cursor, favoritos, privadas e contadores coerentes |
| T11 | `GET /v1/rooms/{roomId}/messages` | ordenacao por cursor, dedupe, id temporario e reconexao |
| T11 | `POST /v1/messages/{id}/task` | converte mensagem em tarefa preservando origem |
| T12 | `PATCH /v1/rooms/{roomId}` | impedir remover ultimo moderador |
| T13 | `GET /v1/rooms/{roomId}/files` | quarantine e signed URL com expiracao |

## Eventos esperados

- `room.message.created`
- `room.message.updated`
- `room.member.changed`
- `room.file.quarantined`
- `room.unread.changed`

## Casos de borda obrigatorios

- reconnect fora de ordem
- upload duplicado
- mencao a membro suspenso
- sala privada nao deve aparecer em busca/contador

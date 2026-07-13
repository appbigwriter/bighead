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

## Ordenacao, cursor e deduplicacao

- Salas, mensagens e arquivos usam ordenacao deterministica `createdAt DESC, id DESC`.
- `cursor` e opaco e representa o ultimo par `(createdAt, id)` recebido. O cliente deve
  reenviar o valor sem decodificar; cursor malformado retorna `422`. `limit` aceita `1..100`
  e o default e `50`. Ausencia de `nextCursor` encerra a navegacao.
- A timeline e devolvida da mais nova para a mais antiga. Ao anexar uma pagina, o cliente
  preserva a ordenacao e elimina repeticoes por `id`.
- `POST /v1/rooms/{roomId}/messages` usa `clientId` (string nao vazia, ate 120 caracteres)
  como chave idempotente no escopo `(tenant, sala, autor)`. Retry com o mesmo `clientId`
  devolve a mensagem ja criada; um novo envio logico deve gerar outro `clientId`.

## Upload de arquivo

1. `POST /v1/artifacts/uploads` recebe
   `{ filename, mimeType, sizeBytes, checksumSha256 }`; `checksumSha256` tem 64 caracteres
   hexadecimais e `sizeBytes` aceita `1..52_428_800` (50 MiB).
2. A resposta `201` contem `{ artifactId, path, uploadUrl, expiresAt, requiredHeaders,
   quarantineStatus: "initiated" }`. O cliente faz `PUT` exatamente em `uploadUrl` com os
   `requiredHeaders`; URL expirada deve reiniciar o passo 1, sem reutilizar a URL.
3. `POST /v1/artifacts/{artifactId}/confirm` recebe o mesmo checksum e retorna `202` com
   `quarantineStatus: "pending"`. Download/preview so e oferecido quando o status e `clean`;
   `rejected` exibe o motivo e permite selecionar outro arquivo.

MIME types aceitos: PDF, PNG, JPEG, WebP, texto simples/Markdown, CSV, JSON, DOCX, XLSX,
PPTX e ZIP. Nome com separador de caminho, checksum divergente, MIME/extensao incompativel
ou tamanho acima do limite retorna `422`; artefato ausente retorna `404`; artefato ainda em
quarentena retorna `409`; URL assinada expirada retorna `410`.

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

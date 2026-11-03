# Panels: `salli.panel/1`

A panel is a screen an extension adds to the phone app and the console, as a
document the server builds, so the clients show it without core knowing the
extension's words. Core validates and serves panels; it never builds one and
never computes a figure in one: every amount is a string the extension
supplies.

`GET /v1/panels` lists the screens `[{id, title, entry}]`, `entry` being
`"more"`, `"settings"` or `null` (reached only from an offer or a link);
`GET /v1/panels/{id}` builds one for the caller. Both are for Salli's own
clients (the app, the console, the CLI, a person's own token), never an agent
connection; both are `no-store`. `/v1/meta` says `panels: true` when there are
any. `salli panels list|show <id>` reads them.

A problem's `offer` (`{title, detail, label, panel}`) names a panel by id:
the client shows `label` and opens that panel.

## The document

```json
{
  "schema": "salli.panel/1",
  "id": "string",
  "title": "string",
  "sections": [{ "heading": "string|null", "rows": [], "footnote": "string|null" }],
  "note": "string|null"
}
```

A row is one of:

| `kind` | Fields |
|---|---|
| `text` | `label`, `value` (string or null) |
| `link` | `label`, `detail` (or null), `url` (https) |
| `action` | `label`, `detail` (or null), `confirm` (asked first, or null), `action`: `{method: "POST"\|"DELETE", path, body: object\|null, then: "refresh"\|"close"}` |
| `form` | `label`, `fields`: `[{name, label, type: "text"\|"number"\|"select", options: [{value, label}]\|null, required}]` (`options` for `select` only), `submit`: `{label, method: "POST", path, then}` |

Limits, all enforced by `domain/panels.py` (`check_panel`): at most 8
sections, 24 rows in each, 24 fields in a form; every string at most 280
characters; `id` a lower-case slug (`[a-z][a-z0-9-]*`); a URL is `https://`; an
action's or submit's `path` starts with `/v1/` and stays on the server (no
other host, no `//`, no `..`). A client sends the action's request to its own
server, with the person's own sign-in; a form's fields go as the JSON body
(`number` as a string, as every amount is). `then` is what the client does
after a success: `refresh` rebuilds the panel, `close` closes it.

## Failing

The builder is the extension's. When it raises, or returns anything that is
not a valid document (or one with another id than the one registered), the
answer is a 500 for that panel, logged with the panel's id; nothing of the
document is sent, the list and every other panel keep working, and a client
shows its own "could not load" state.

## Registering

```python
Extension(name="x", panels=[PanelSpec("account", "Your account", builder, entry="more")])
```

`builder` is `async (user_id) -> dict`. An id belongs to one extension.

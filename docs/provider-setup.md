# Provider setup (Luna and Haiku only)

Do not paste API keys into git, issues, or episode records.

## Allowed models

| Provider | Model id |
| --- | --- |
| OpenAI | `gpt-5.6-luna` |
| Anthropic | `claude-haiku-4-5-20251001` (aliases `claude-haiku-4-5`, `claude-haiku-4.5`) |

Sol, Terra, Sonnet, and Opus are rejected when constructing `ProviderConfig`.

## Local config

```sh
cp .env.example .env
python3 -m controlled_ai.providers
```

The dry-run prints whether each key is present and which model is pinned. It does not call the network.

Live calls also require both of:

```sh
export CONTROLLED_AI_ENABLE_NETWORK=1
export CONTROLLED_AI_VALIDATE_PROVIDER_WIRE=1
```

Leave those unset until the dry-run shows the pinned models. The finite prototype tests stay local either way.

# LLM Client Test Report

**Generated:** 2026-04-08T20:35:40.118122
**Total Tests:** 14
**Results:** 3 Passed, 11 Failed, 0 Skipped

---

## Test Results

### Deep Think

**Summary:** 0 passed, 3 failed, 0 skipped

| Status | Test ID | Message | Details |
|--------|---------|---------|---------|
| ✗ | `deep_think_001` | Exception: Error code: 400 - {'type': 'error', 'error': {'type': 'bad_request_error', 'message': "invalid params, unknown model 'kimi-k2.5' (2013)", 'http_code': '400'}, 'request_id': '06257e99801cd61f3bc58b552197527a'} |  |
| ✗ | `deep_think_002` | Some reasoning effort levels failed | {'low': 'error: Error code: 400 - {\'type\': \'error\', \'error\': {\'type\': \'bad_request_error\', \'message\': "invalid params, unknown model \'kimi-k2.5\' (2013)", \'http_code\': \'400\'}, \'request_id\': \'06257e9919df301641553ebabb241395\'}', 'medium': 'error: Error code: 400 - {\'type\': \'error\', \'error\': {\'type\': \'bad_request_error\', \'message\': "invalid params, unknown model \'kimi-k2.5\' (2013)", \'http_code\': \'400\'}, \'request_id\': \'06257e99a2d3fb56bc51528cac346c53\'}', 'high': 'error: Error code: 400 - {\'type\': \'error\', \'error\': {\'type\': \'bad_request_error\', \'message\': "invalid params, unknown model \'kimi-k2.5\' (2013)", \'http_code\': \'400\'}, \'request_id\': \'06257e99eee4718e52ad1b0932ad8d99\'}'} |
| ✗ | `deep_think_003` | Comparison failed: Error code: 400 - {'type': 'error', 'error': {'type': 'bad_request_error', 'message': "invalid params, unknown model 'kimi-k2.5' (2013)", 'http_code': '400'}, 'request_id': '06257e9907946a9decda3adc23966373'} |  |

### Init

**Summary:** 2 passed, 0 failed, 0 skipped

| Status | Test ID | Message | Details |
|--------|---------|---------|---------|
| ✓ | `init_001` | Client initialized successfully | Model: kimi-k2.5 |
| ✓ | `init_002` | Model validation completed | Result: False |

### Retry

**Summary:** 1 passed, 2 failed, 0 skipped

| Status | Test ID | Message | Details |
|--------|---------|---------|---------|
| ✗ | `retry_001` | Retry mechanism failed: Error code: 400 - {'type': 'error', 'error': {'type': 'bad_request_error', 'message': "invalid params, unknown model 'kimi-k2.5' (2013)", 'http_code': '400'}, 'request_id': '06257e9ab8a117b8bf54c695cfa73d97'} |  |
| ✗ | `retry_002` | Retry configs not working | {"{'max_retries': 1, 'timeout': 3}": 'error: Error code: 400 - {\'type\': \'error\', \'error\': {\'type\': \'bad_request_error\', \'message\': "invalid params, unknown model \'kimi-k2.5\' (2013)", \'http_code\': \'400\'}, \'request_id\': \'06257e9b1703e69d57c3cadb82e530ed\'}', "{'max_retries': 3, 'timeout': 5}": 'error: Error code: 400 - {\'type\': \'error\', \'error\': {\'type\': \'bad_request_error\', \'message\': "invalid params, unknown model \'kimi-k2.5\' (2013)", \'http_code\': \'400\'}, \'request_id\': \'06257e9b652fb631ca99e86fbe323691\'}', "{'max_retries': 5, 'timeout': 10}": 'error: Error code: 400 - {\'type\': \'error\', \'error\': {\'type\': \'bad_request_error\', \'message\': "invalid params, unknown model \'kimi-k2.5\' (2013)", \'http_code\': \'400\'}, \'request_id\': \'06257e9b9e4442292e94f4b3be179b2c\'}'} |
| ✓ | `retry_003` | Error handled gracefully | Time: 0.24s |

### Stream

**Summary:** 0 passed, 3 failed, 0 skipped

| Status | Test ID | Message | Details |
|--------|---------|---------|---------|
| ✗ | `stream_001` | Exception: Error code: 400 - {'type': 'error', 'error': {'type': 'bad_request_error', 'message': "invalid params, unknown model 'kimi-k2.5' (2013)", 'http_code': '400'}, 'request_id': '06257e9abf4947ffabc96cf9e5f26d7b'} |  |
| ✗ | `stream_002` | Exception: Error code: 400 - {'type': 'error', 'error': {'type': 'bad_request_error', 'message': "invalid params, unknown model 'kimi-k2.5' (2013)", 'http_code': '400'}, 'request_id': '06257e9a4590c7a013d7cf7ddee50c63'} |  |
| ✗ | `stream_003` | Exception: Error code: 400 - {'type': 'error', 'error': {'type': 'bad_request_error', 'message': "invalid params, unknown model 'kimi-k2.5' (2013)", 'http_code': '400'}, 'request_id': '06257e9a044872cf4ed2c8bd4c769235'} |  |

### Token

**Summary:** 0 passed, 3 failed, 0 skipped

| Status | Test ID | Message | Details |
|--------|---------|---------|---------|
| ✗ | `token_001` | Exception: Error code: 400 - {'type': 'error', 'error': {'type': 'bad_request_error', 'message': "invalid params, unknown model 'kimi-k2.5' (2013)", 'http_code': '400'}, 'request_id': '06257e99ba1ac3574421c82973fa0695'} |  |
| ✗ | `token_002` | Exception: Error code: 400 - {'type': 'error', 'error': {'type': 'bad_request_error', 'message': "invalid params, unknown model 'kimi-k2.5' (2013)", 'http_code': '400'}, 'request_id': '06257e9aa90651ead1d42e1ea5b3d4c9'} |  |
| ✗ | `token_003` | Exception: Error code: 400 - {'type': 'error', 'error': {'type': 'bad_request_error', 'message': "invalid params, unknown model 'kimi-k2.5' (2013)", 'http_code': '400'}, 'request_id': '06257e9af4f6b1a090c6f0ccd94da373'} |  |

## Token Usage Statistics (Last 24h)

- **Total Requests:** 161
- **Total Prompt Tokens:** 638,876
- **Total Completion Tokens:** 127,957
- **Total Cost:** ¥0.383413


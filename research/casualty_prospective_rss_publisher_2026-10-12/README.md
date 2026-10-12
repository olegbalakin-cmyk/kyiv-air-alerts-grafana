# Isolated prospective RSS and publisher observation

Single bounded live observation. Original response entity bytes are held in raw/, never inferred from XML, requests.text or a web search. HTTP framing and TLS packets are not captured. Redirect headers are metadata. Raw responses may be content-encoded and no transcoding is performed. Captured at client-side UTC wall clocks with microsecond formatting, not independently calibrated. Historical first availability and production ingestion are NOT OBSERVABLE.

Verify: python validate_offline.py --root .

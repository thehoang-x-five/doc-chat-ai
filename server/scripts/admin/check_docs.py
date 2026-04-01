import httpx
import asyncio
import json

async def check():
    async with httpx.AsyncClient(base_url='http://localhost:8000', timeout=60.0) as client:
        r = await client.post('/api/v1/auth/login', json={'email':'test@example.com','password':'test123'})
        token = r.json()['access_token']
        
        r = await client.get('/api/v1/documents', params={'workspace_id':'651d9005-11db-41fd-bacd-74b6b96c7f64'}, headers={'Authorization':f'Bearer {token}'})
        docs = r.json()
        
        print(f'Total documents: {len(docs)}')
        print(f'Response type: {type(docs)}')
        
        if isinstance(docs, list) and len(docs) > 0:
            print(f'\nFirst doc keys: {docs[0].keys() if isinstance(docs[0], dict) else "not a dict"}')
            print(f'\nFirst doc: {json.dumps(docs[0], indent=2, default=str)}')
            
            # Check for processing docs
            for d in docs:
                if isinstance(d, dict):
                    status = d.get('status', 'unknown')
                    name = d.get('name') or d.get('originalName') or 'NO NAME'
                    print(f'  - {name}: {status}')
        else:
            print(f'Response: {docs}')

asyncio.run(check())

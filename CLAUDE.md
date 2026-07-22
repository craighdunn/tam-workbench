# TAM Workbench — Claude Code Instructions                                                  

## Project                                                                                  

TAM Workbench is a local Streamlit + SQLite dashboard/workbench for Technical Account       
Management at Showpad.                                                                                  

It is used by Craig Dunn for account management, contacts, tasks, notes, dashboard views,   
and coworker-facing install packages.                                                                   

## Tech stack                                                                               

- Python 3.11+                                                                              
- uv                                                                                        
- Streamlit dashboard                                                                       
- SQLite local persistence                                                                  
- pytest tests                                                                              

## Key commands                                                                             

Run tests:                                                                                  

```bash                                                                                     
uv run pytest -q                                                                            
```                                                                                         

Run dashboard:                                                                              

```bash                                                                                     
uv run tam-workbench-dashboard                                                              
```                                                                                         

Build coworker package:                                                                     

```bash                                                                                     
./scripts/build-coworker-package.sh                                                         
```                                                                                         

Dashboard URL:                                                                              

```text                                                                                     
http://localhost:8501                                                                       
```                                                                                         

## Important files                                                                          

- `src/tam_workbench/dashboard.py` — main dashboard UI and async save bridge                
- `src/tam_workbench/db.py` — SQLite schema, migrations, persistence helpers                
- `src/tam_workbench/dashboard_data.py` — data shaping for dashboard                        
- `src/tam_workbench/server.py` — server/MCP-facing tool definitions                        
- `src/tam_workbench/tools.py` — tool wrapper logic                                         
- `tests/` — regression tests                                                               
- `CHANGELOG.md` — update on versioned changes                                              
- `pyproject.toml` — package version                                                        
- `scripts/build-coworker-package.sh` — coworker fresh-install package builder              

## Current source of truth                                                                  

Use the GitHub-connected repo as the active project folder:                                 

```bash                                                                                     
/Users/craigdunn/CoworkOS/tam-workbench-github/tam-workbench                                
```                                                                                         

GitHub repo:                                                                                

```text                                                                                     
https://github.com/craighdunn/tam-workbench                                                 
```                                                                                         

The older non-Git working folder may still exist here:                                      

```bash                                                                                     
/Users/craigdunn/CoworkOS/tam-workbench                                                     
```                                                                                         

Treat that older folder as a backup/archive unless Craig explicitly asks otherwise.         

## Current version                                                                          

Current handoff version:                                                                    

```text                                                                                     
v0.3.8                                                                                      
```                                                                                         

v0.3.8 includes editable contact Supporter Level and Showpad Owner fields.                  

## Product rules                                                                            

- Prefer archive/hide over hard deletes.                                                    
- Archived accounts, tasks, contacts, and notes should not appear in the dashboard or       
normal list/search flows.                                                                               
- Dashboard saves should stay in-page and must not open new browser tabs.                   
- Contact sections should show **Clients** above **Showpad Account Team**.                  
- Contacts should support:                                                                  
- Contact Type: Client Contact or Showpad Contact                                         
- Supporter Level: Champion, Supporter, Neutral, Detractor                                
- Showpad Owner checkbox                                                                  
- Showpad Owner means the customer-side main Showpad admin/platform owner.                  
- Only one contact per account should be marked Showpad Owner at a time.                    
- Account sidebar should be sorted alphabetically.                                          
- Account health label should be **Task Health**.                                           
- Task Health is derived from local task/workbench signals, not official Showpad customer   
health.                                                                                                 
- Search input should preserve cursor/caret position while filtering.                       
- Dashboard edits should use in-page panels/fields, not browser prompts or disruptive       
refreshes.                                                                                              

## Contact model notes                                                                      

Contact fields include:                                                                     

- name                                                                                      
- title                                                                                     
- role                                                                                      
- email                                                                                     
- phone                                                                                     
- notes                                                                                     
- is_primary                                                                                
- support_level                                                                             
- is_showpad_owner                                                                          
- archived_at                                                                               

Supporter Level options:                                                                    

```text                                                                                     
champion                                                                                    
supporter                                                                                   
neutral                                                                                     
detractor                                                                                   
```                                                                                         

Display labels:                                                                             

```text                                                                                     
Champion                                                                                    
Supporter                                                                                   
Neutral                                                                                     
Detractor                                                                                   
```                                                                                         

Showpad Owner is stored as a boolean/integer field:                                         

```text                                                                                     
is_showpad_owner                                                                            
```                                                                                         

When setting one contact as Showpad Owner, unset other contacts on the same account.        

## Dashboard behavior notes                                                                 

The dashboard uses an imported/custom HTML dashboard shell inside Streamlit.                

Important behaviors:                                                                        

- The dashboard iframe uses an async local save bridge.                                     
- Saves are sent via `fetch` to a local endpoint.                                           
- Avoid query-param save flows that cause new tabs or page navigation.                      
- Keep dashboard interactions app-like and in-place.                                        
- Contact, task, note, and account edit actions should render inside the dashboard UI.      

## Testing expectations                                                                     

Before changing behavior, establish baseline:                                               

```bash                                                                                     
git status --short --branch                                                                 
uv run pytest -q                                                                            
```                                                                                         

After changes:                                                                              

```bash                                                                                     
uv run pytest -q                                                                            
```                                                                                         

For dashboard/UI persistence changes, also verify either:                                   

- generated HTML contains the expected controls/handlers, and/or                            
- browser behavior works locally at `http://localhost:8501`, and/or                         
- SQLite contains the expected persisted values.                                            

## Packaging expectations                                                                   

When making a versioned coworker-facing change:                                             

1. Update `pyproject.toml`.                                                                 
2. Update `CHANGELOG.md`.                                                                   
3. Update `scripts/build-coworker-package.sh` ZIP version if needed.                        
4. Run:                                                                                     

```bash                                                                                     
uv lock                                                                                     
uv run pytest -q                                                                            
./scripts/build-coworker-package.sh                                                         
```                                                                                         

5. Verify the extracted package:                                                            

```bash                                                                                     
rm -rf /tmp/tam-workbench-verify                                                            
mkdir -p /tmp/tam-workbench-verify                                                          
unzip -q dist/tam-workbench-vX.Y.Z-fresh-install.zip -d /tmp/tam-workbench-verify           
cd /tmp/tam-workbench-verify/tam-workbench                                                  
uv sync --dev                                                                               
uv run pytest -q                                                                            
```                                                                                         

## Git safety                                                                               

Before making changes:                                                                      

```bash                                                                                     
git status --short --branch                                                                 
git remote -v                                                                               
```                                                                                         

Before pushing:                                                                             

```bash                                                                                     
uv run pytest -q                                                                            
git diff --stat                                                                             
git status --short --branch                                                                 
```                                                                                         

Do not commit:                                                                              

- `.venv/`                                                                                  
- `.pytest_cache/`                                                                          
- `__pycache__/`                                                                            
- `.tam-workbench/`                                                                         
- `*.db`                                                                                    
- `*.sqlite`                                                                                
- `*.sqlite3`                                                                               
- `dist/`                                                                                   
- `build/`                                                                                  
- `.env`                                                                                    
- `.env.*`                                                                                  
- secrets                                                                                   
- credentials                                                                               
- logs                                                                                      

Safety grep:                                                                                

```bash                                                                                     
git ls-files | grep -E                                                                      
'(^|/)(\.venv|__pycache__|\.pytest_cache|dist|build|\.DS_Store)|\.(db|sqlite|sqlite3)$|dobby-auth-profi 
les\.json|\.env' || true                                                                                
```                                                                                         

Note: this may flag `scripts/build-coworker-package.sh` because the path contains `build`;  
that script is intended source and is okay.                                                             

## Normal workflow                                                                          

Use this folder:                                                                            

```bash                                                                                     
cd /Users/craigdunn/CoworkOS/tam-workbench-github/tam-workbench                             
```                                                                                         

Pull first:                                                                                 

```bash                                                                                     
git pull                                                                                    
```                                                                                         

Run tests:                                                                                  

```bash                                                                                     
uv run pytest -q                                                                            
```                                                                                         

Make changes, then:                                                                         

```bash                                                                                     
uv run pytest -q                                                                            
git status --short --branch                                                                 
git diff --stat                                                                             
git add .                                                                                   
git commit -m "Describe the change"                                                         
git push                                                                                    
```                                                                                         

## Response preferences for Craig                                                           

- Be clear and direct, but use a softer/gentler tone when correcting misunderstandings.     
- Admit uncertainty rather than guessing.                                                   
- If something cannot be verified, say what is missing and why.                             
- Prefer working artifacts and verified results over plans alone.                           
- For UI work, verify the dashboard actually runs and behaves correctly when possible.  
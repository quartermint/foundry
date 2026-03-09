# Code Conventions

## Python Backend

### Style
- Standard Python formatting (no formatter config found, but consistent style)
- Type hints used throughout (Python 3.10+ union syntax: `str | None`)
- `Mapped[Type]` with `mapped_column()` for SQLAlchemy models
- `from __future__ import annotations` NOT used
- Logging via `logging.getLogger(__name__)` in every module

### Patterns

**Router pattern:**
```python
router = APIRouter(
    prefix="/api/resource",
    tags=["resource"],
    dependencies=[Depends(require_token)]
)

@router.get("")
async def list_items(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Model).order_by(Model.created_at.desc()))
    return [item.to_dict() for item in result.scalars().all()]
```

**Model pattern:**
```python
class MyModel(Base):
    __tablename__ = "my_models"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, ...}
```

**Service pattern:**
- Services are either module-level functions or singleton class instances
- Singletons: `mqtt_service = BambuMQTTService()`, `blender_mcp = BlenderMCPClient()`
- Module functions: `generate_thumbnail()`, `slice_stl()`, `notify()`
- AI functions: `async def generate_search_queries(description: str) -> list[str]`

**Pydantic request bodies:**
```python
class CreateRequest(BaseModel):
    name: str
    optional_field: str | None = None
    with_default: int = 42
```

### Error Handling
- `HTTPException` raised in routers for API errors
- `logger.exception()` for unexpected errors (includes traceback)
- `try/except Exception` blocks around external service calls
- Background jobs wrap entire execution in try/except
- Services return `None`, `False`, or result dicts to indicate failure (not exceptions)

### Async Patterns
- All router handlers are `async def`
- `asyncio.create_subprocess_exec()` for CLI tools (OpenSCAD, OrcaSlicer, yt-dlp)
- `asyncio.wait_for()` with timeout for subprocess communication
- `asyncio.gather()` for parallel platform searches
- MQTT uses daemon threads bridged to asyncio via `loop.call_soon_threadsafe()`

## TypeScript Frontend

### Style
- Strict TypeScript (`strict: true`, `noUnusedLocals`, `noUnusedParameters`)
- Functional components with hooks
- Inline interfaces (defined in same file, not shared)
- Template literals for classNames with Tailwind
- SVG icons inline (no icon library)

### Patterns

**Page pattern:**
```tsx
export default function PageName() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['resource'],
    queryFn: () => apiFetch<Type[]>('/api/resource'),
    retry: 1,
  })

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-zinc-100">Title</h1>
        <p className="text-sm text-zinc-400 mt-1">Subtitle</p>
      </div>
      {isLoading && <Spinner />}
      {error && <ErrorMessage />}
      {data && data.length === 0 && <EmptyState />}
      {data && data.length > 0 && <DataGrid />}
    </div>
  )
}
```

**API client pattern:**
```typescript
export async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const token = getToken()
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  })
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}
```

**Mutation pattern:**
```tsx
const mutation = useMutation({
  mutationFn: (data: InputType) => apiFetch<ResponseType>('/api/path', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['resource'] })
  },
})
```

### UI Conventions
- **Dark theme:** zinc-900 backgrounds, zinc-700 borders, zinc-100 text
- **Accent colors:** emerald (primary actions), sky (printing/send), violet (generation), orange (blender), red (errors), amber (warnings)
- **Status badges:** Colored `px-2 py-0.5 rounded-full text-xs font-medium` with `bg-{color}-500/15 text-{color}-400`
- **Cards:** `bg-zinc-900 border border-zinc-700 rounded-xl p-5 shadow-lg shadow-black/20`
- **Buttons:** `px-4 py-2 bg-{color}-600 hover:bg-{color}-500 text-white rounded-lg text-sm font-medium`
- **Inputs:** `bg-zinc-800 border border-zinc-600 rounded-lg px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-{color}-500`
- **Loading spinners:** `border-2 border-zinc-600 border-t-{color}-400 rounded-full animate-spin`
- **Sidebar:** 16px collapsed, 240px expanded, hover-triggered

### State Management
- Server state: TanStack Query (`useQuery` + `useMutation`)
- Local state: `useState` for UI interactions (tabs, forms, drag state)
- Auth token: `localStorage.getItem('foundry_token')`
- No global state store (no Redux, Zustand, etc.)
- WebSocket managed via custom `usePrinterStatus` hook with auto-reconnect

## Commit & Git Conventions
- Single branch (main)
- No commit hooks configured
- `.gitignore` covers venv, node_modules, dist, storage, logs, .env

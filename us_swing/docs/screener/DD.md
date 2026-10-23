# Design Document — Screener (SCR)

**Document ID:** DD-SCR
**Version:** 2.1.1
**Traces To:** SRD-SCR v2.1.0
**Status:** Draft
**Last Updated:** 2026-05-23
**Project:** US Swing Trading System

---

# FO-SCR-001 — Preset Model & Data Structures

## DD-SCR-001.001.D01 — Preset Data Model & Serialization
- **Status:** Approved

**Parent SRDs:** SRD-SCR-001.001 through SRD-SCR-001.008

### Data Structures

```python
@dataclass
class ScreenerRef:
    """Reference to a screener within a preset."""
    screener_id: str                    # e.g., "indicator_composite", "ml_v3", "llm_claude_ranking"
    screener_type: str                  # e.g., "indicator", "ml", "llm_claude"
    enabled: bool = True                # Can disable without removing
    config: dict = field(default_factory=dict)  # Screener-specific params
    weight: float = 1.0                 # For weighted presets only

@dataclass
class ScreenerGroup:
    """Group of screeners in a Composite preset (AND/OR logic)."""
    id: str                             # e.g., "group_1", "momentum_group"
    logic: Literal["AND", "OR"]         # Combined logic within group
    screeners: list[ScreenerRef]        # Screeners in this group

@dataclass
class Preset:
    """User or admin-created preset defining screening rules."""
    id: str                             # Unique ID (UUID or slug)
    name: str                           # Human-readable name
    description: str = ""               # Optional notes
    preset_type: Literal["Composite", "Weighted"] = "Composite"
    
    # For Composite presets
    groups: list[ScreenerGroup] = field(default_factory=list)
    
    # For Weighted presets
    screeners: list[ScreenerRef] = field(default_factory=list)
    weights: dict[str, float] = field(default_factory=dict)  # {screener_id: weight}
    threshold: float = 0.5              # Pass if score >= threshold
    
    # Metadata
    created_by: str = ""                # user_id or "admin"
    is_admin: bool = False              # Admin presets read-only to users
    is_shared: bool = False             # Can be shared with other users
    assigned_to: list[str] = field(default_factory=list)  # user_ids with access
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    enabled: bool = True                # Can be disabled without deletion
    
    def to_dict(self) -> dict:
        """Serialize to JSON-compatible dict."""
        # All datetimes → ISO-8601 strings
        # Enums → strings
        # Return dict suitable for json.dump()
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Preset':
        """Deserialize from dict (after JSON load)."""
        # ISO-8601 strings → datetime
        # String enums → Literal types
        # Validation on load
    
    def validate(self) -> None:
        """Validate structural and data integrity."""
        # Check preset_type matches structure
        # Verify all screener_ids in registry
        # For Weighted: weights sum to ~1.0, threshold in [0, 1]
        # Raise PresetValidationError if invalid
```

### Serialization Strategy

- **Format:** JSON only (no YAML, no Python dataclasses in files)
- **Storage paths:**
  - Admin: `~/.usswing/screener_results/presets_admin/{id}.json`
  - User: `~/.usswing/screener_results/presets_user/{user_id}/{id}.json`
- **File format:** Full `Preset` object serialized (not metadata-only)
- **Datetimes:** ISO-8601 strings (e.g., "2026-04-16T10:30:00Z")
- **Enums:** Strings (e.g., "AND", "Composite")
- **Round-trip guarantee:** `Preset.from_dict(preset.to_dict())` produces equal instance

---

## DD-SCR-001.009.D01 — trading_styles Field in Preset
- **Status:** Draft

**Parent SRD:** SRD-SCR-001.009

### Dataclass Amendment

`trading_styles` is added to the `Preset` dataclass between `enabled` and `created_at`:

```python
@dataclass
class Preset:
    ...
    trading_styles: list[Literal["swing", "day", "position"]] = field(default_factory=list)
    ...
```

### Validation

`Preset.validate()` gains one additional check:

```python
_VALID_STYLES: frozenset[str] = frozenset({"swing", "day", "position"})

def validate(self) -> None:
    # ... existing checks ...
    unknown = set(self.trading_styles) - _VALID_STYLES
    if unknown:
        raise PresetValidationError(f"Unknown trading styles: {unknown!r}")
```

### Serialization

- `to_dict()` emits `"trading_styles": ["swing", "day"]` (list of strings; empty list when untagged)
- `from_dict()` reads `data.get("trading_styles", [])` — backward-compatible with existing JSON files that lack the field

Round-trip: `Preset.from_dict(p.to_dict()).trading_styles == p.trading_styles` guaranteed.

---

# FO-SCR-002 — Plugin-Based Screener Architecture

## DD-SCR-002.001.D01 — Screener Plugin Architecture
- **Status:** Approved

**Parent SRDs:** SRD-SCR-002.001 through SRD-SCR-002.008

### Screener Protocol

```python
from typing import Protocol, Literal

class Screener(Protocol):
    """Base protocol all screener implementations conform to."""
    
    screener_id: str                    # e.g., "indicator_composite", "ml_v3"
    screener_type: str                  # e.g., "indicator", "ml", "llm_claude"
    name: str                           # Human-readable name
    
    def apply(
        self,
        symbols: list[str],
        bars: dict[str, list[OHLCVBar]],  # {symbol: [candles 1d/1w]}
        config: dict
    ) -> dict[str, tuple[bool, float]]:
        """
        Filter and score symbols.
        
        Args:
            symbols: list of S&P 500 symbols
            bars: historical bars per symbol (dict keyed by symbol)
            config: screener-specific parameters
        
        Returns:
            {symbol: (passed: bool, score: 0–1), ...}
            All symbols must be in output (disabled symbols: (False, 0.0))
        
        Raises:
            ScreenerError if config invalid or data insufficient
        """
    
    def batch_features(
        self,
        symbols: list[str],
        bars: dict[str, list[OHLCVBar]],
        config: dict
    ) -> dict[str, dict]:
        """
        Extract features for LLM ranking (optional).
        
        Args:
            symbols: list of symbols (typically ~20 top candidates)
            bars: bars for those symbols
            config: screener config
        
        Returns:
            {symbol: {feature_name: value, ...}, ...}
            Default: return empty dict (no features)
        """
```

### ScreenerRegistry

```python
class ScreenerRegistry:
    """Central registry of available screeners (singleton)."""
    
    _screeners: dict[str, type[Screener]] = {}
    
    @classmethod
    def register(cls, screener_id: str, screener_class: type[Screener]) -> None:
        """Register a screener plugin."""
        cls._screeners[screener_id] = screener_class
    
    @classmethod
    def get(cls, screener_id: str) -> Screener:
        """Instantiate and return screener by ID."""
        if screener_id not in cls._screeners:
            raise ScreenerNotFoundError(f"Screener {screener_id} not found")
        return cls._screeners[screener_id]()
    
    @classmethod
    def list_available(cls) -> dict[str, str]:
        """Return {screener_id: name} for all registered screeners."""
        return {sid: cls.get(sid).name for sid in cls._screeners}
```

### Built-In Screeners

```python
class IndicatorScreener(Screener):
    """Wraps v1 filter logic as v2 plugin."""
    screener_id = "indicator_composite"
    screener_type = "indicator"
    name = "Technical Indicators (RSI, ATR, Range, Breakout, Volume)"
    
    def apply(symbols, bars, config):
        # config: {
        #   "volatility_enabled": bool,
        #   "rsi_enabled": bool,
        #   "rsi_min": float,
        #   "rsi_max": float,
        #   "atr_period": int,
        #   "atr_lookback": int,
        #   ... (all v1 ScreenerConfig params)
        # }
        # Reuse v1 filters (VolatilityFilter, RSIFilter, etc.)
        # Return identical results to v1 ScreenerEngine

class MLScreener(Screener):
    screener_id = "ml_ensemble_v3"
    screener_type = "ml"
    name = "ML Ensemble Model v3"
    
    def apply(symbols, bars, config):
        # config: {"model_path": "path/to/model.pkl", "feature_set": "v3", ...}
        # Load model from config["model_path"]
        # Extract features from bars
        # Inference (vectorized, not per-symbol)
        # Return {symbol: (score >= threshold, score), ...}
    
    def batch_features(symbols, bars, config):
        # Extract and cache features
        # Returns {symbol: {feature_name: value}}

class LLMClaudeScreener(Screener):
    screener_id = "llm_claude_ranking"
    screener_type = "llm_claude"
    name = "Claude LLM Ranking"
    
    def apply(symbols, bars, config):
        # Note: not used for binary filtering; used for ranking only
        # Returns all symbols as passed with confidence score
        # {symbol: (True, confidence), ...}
    
    def batch_features(symbols, bars, config):
        # Extract: price, trend, RSI, ATR, support/resistance, volume
        # Returns {symbol: {price: ..., trend: ..., ...}}
```

---

# FO-SCR-003 — Three-Stage Execution Pipeline

## DD-SCR-003.001.D01 — Three-Stage Execution Pipeline
- **Status:** Approved

**Parent SRDs:** SRD-SCR-003.001 through SRD-SCR-003.008

### Stage 1: Pre-Filter

```python
class PreFilter:
    """Quick, single-threaded pre-filter."""
    
    @staticmethod
    def apply(
        symbols: list[str],
        bars: dict[str, list[OHLCVBar]]
    ) -> list[str]:
        """
        Quick filters: price > $5, volume > 1M, not halted.
        Returns ~300 symbols from 500 in <1s.
        """
        filtered = []
        for symbol in symbols:
            if symbol not in bars or not bars[symbol]:
                continue
            last_bar = bars[symbol][-1]
            if last_bar.close > 5 and last_bar.volume > 1_000_000:
                # Not halted check (if available in bar metadata)
                filtered.append(symbol)
        return filtered
```

### Stage 2: Parallel Execution

```python
class PresetExecutor:
    """Orchestrates 3-stage pipeline."""
    
    def __init__(self, db: DatabaseManager, app_service: AppService):
        self.db = db
        self.app_service = app_service
    
    def run_preset(
        self,
        preset_id: str,
        user_id: str,
        manual: bool = False
    ) -> ScreenerRunResult:
        """Main entry point: execute 3-stage pipeline."""
        
        # Step 1: Load preset, validate permissions
        pm = PresetManager()
        preset = pm.load_preset(preset_id, user_id)  # Raises PresetAccessDenied if no access
        
        # Step 2: Fetch universe and candles
        universe = self.app_service.get_universe()  # Returns ~500 symbols
        bars_1d = {}
        for sym in universe:
            bars_1d[sym] = self.db.fetch_bars(sym, '1d', limit=500)  # ~2 years
        
        # Step 3: Stage 1 — Pre-Filter
        start_time = time.time()
        filtered = PreFilter.apply(universe, bars_1d)
        prefilter_time = time.time() - start_time
        
        # Step 4: Stage 2 — Parallel Execution
        stage2_start = time.time()
        stage2_results = self._run_stage2(preset, filtered, bars_1d)
        stage2_time = time.time() - stage2_start
        
        # Step 5: Stage 3 — Optional LLM Ranking
        stage3_results = {}
        stage3_time = 0
        if self._should_run_llm_ranking(preset):
            stage3_start = time.time()
            stage3_results = self._run_stage3(preset, stage2_results, bars_1d, filtered)
            stage3_time = time.time() - stage3_start
        
        # Step 6: Serialize result and persist
        result = ScreenerRunResult(
            preset_id=preset_id,
            preset_type=preset.preset_type,
            run_timestamp=datetime.now(timezone.utc),
            execution_mode="manual" if manual else "scheduled",
            total_symbols_screened=len(universe),
            symbols_after_prefilter=len(filtered),
            passed_count=len([r for r in stage2_results.values() if r['passed']]),
            results=stage2_results,  # or stage3_results if ranked
            execution_times={
                'pre_filter_ms': prefilter_time * 1000,
                'stage2_ms': stage2_time * 1000,
                'stage3_ms': stage3_time * 1000,
            }
        )
        
        # Persist and emit event
        storage = ScreenerResultsStorage()
        storage.save_result(result)
        # emit_event("screener_run_completed", preset_id=preset_id, result=result)
        
        return result
    
    def _run_stage2(self, preset, symbols, bars_1d):
        """Parallel screener execution (composite/weighted logic)."""
        # Instantiate screeners from registry
        screeners = {}
        for screener_ref in self._collect_screener_refs(preset):
            if not screener_ref.enabled:
                continue
            screener = ScreenerRegistry.get(screener_ref.screener_id)
            screeners[screener_ref.screener_id] = (screener, screener_ref.config)
        
        # Parallel execution: multiprocessing for CPU, asyncio for I/O
        results = self._execute_screeners_parallel(screeners, symbols, bars_1d)
        
        # Apply preset logic (Composite AND/OR or Weighted scoring)
        if preset.preset_type == "Composite":
            return self._apply_composite_logic(preset, results)
        else:  # Weighted
            return self._apply_weighted_logic(preset, results)
    
    def _run_stage3(self, preset, stage2_results, bars_1d, symbols):
        """LLM ranking (optional)."""
        # Find LLM screener
        llm_screener_ref = None
        for ref in self._collect_screener_refs(preset):
            if ref.screener_type in ("llm_claude", "llm_local"):
                llm_screener_ref = ref
                break
        
        if not llm_screener_ref:
            return stage2_results  # No LLM ranking
        
        try:
            # Symbols that passed Stage 2
            passed_symbols = [s for s, r in stage2_results.items() if r['passed']]
            if not passed_symbols:
                return stage2_results
            
            # Extract features (batch, cached)
            llm_screener = ScreenerRegistry.get(llm_screener_ref.screener_id)
            features = llm_screener.batch_features(
                passed_symbols,
                {s: bars_1d[s] for s in passed_symbols},
                llm_screener_ref.config
            )
            
            # Cache features
            fc = FeatureCache()
            for symbol, feat in features.items():
                fc.set(datetime.now().date(), symbol, feat)
            
            # Call LLM
            ranking = llm_screener.apply(passed_symbols, bars_1d, llm_screener_ref.config)
            
            # Log API usage
            tracker = APIUsageTracker()
            tracker.log_usage(preset.id, tokens_in=..., tokens_out=...)
            
            # Augment results with ranking
            top_n = llm_screener_ref.config.get('top_n', 5)
            ranked = sorted(ranking.items(), key=lambda x: x[1][1], reverse=True)[:top_n]
            for i, (symbol, (_, score)) in enumerate(ranked):
                stage2_results[symbol]['llm_rank'] = i + 1
                stage2_results[symbol]['llm_score'] = score
            
            return stage2_results
        
        except Exception as e:
            logger.error(f"LLM ranking failed: {e}. Continuing with unranked results.")
            return stage2_results  # Fallback: unranked
```

---

# FO-SCR-004 — Hybrid Execution Modes

## DD-SCR-004.001.D01 — PresetManager & Permissions
- **Status:** Approved

**Parent SRDs:** SRD-SCR-005.001 through SRD-SCR-005.008

```python
class PresetManager:
    """Manages preset CRUD and permissions."""
    
    def __init__(self):
        self.admin_dir = Path.home() / ".usswing" / "screener_results" / "presets_admin"
        self.user_dir = Path.home() / ".usswing" / "screener_results" / "presets_user"
        self.admin_dir.mkdir(parents=True, exist_ok=True)
        self.user_dir.mkdir(parents=True, exist_ok=True)
    
    def create_preset(self, preset: Preset, user_id: str) -> str:
        """Create and persist a preset. Return preset_id."""
        if preset.is_admin and not is_admin(user_id):
            raise PresetAccessDenied("Only admins can create admin presets")
        
        preset.validate()  # Validate screener IDs, logic
        preset.created_by = user_id if not preset.is_admin else "admin"
        preset.created_at = preset.updated_at = datetime.now(timezone.utc)
        
        # Generate ID if missing
        if not preset.id:
            preset.id = str(uuid.uuid4())[:8]
        
        # Determine save path
        if preset.is_admin:
            path = self.admin_dir / f"{preset.id}.json"
        else:
            path = self.user_dir / user_id / f"{preset.id}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
        
        # Atomic write
        self._atomic_write(path, preset.to_dict())
        return preset.id
    
    def load_preset(self, preset_id: str, user_id: str) -> Preset:
        """Load preset. Check permissions."""
        # Try admin first, then user
        admin_path = self.admin_dir / f"{preset_id}.json"
        if admin_path.exists():
            data = self._read_json(admin_path)
            return Preset.from_dict(data)  # Admin presets public
        
        # User preset
        user_path = self.user_dir / user_id / f"{preset_id}.json"
        if user_path.exists():
            data = self._read_json(user_path)
            preset = Preset.from_dict(data)
            # Check if user is creator or in assigned_to
            if user_id != preset.created_by and user_id not in preset.assigned_to:
                raise PresetAccessDenied(f"User {user_id} not permitted to load preset {preset_id}")
            return preset
        
        # Search other user's shared presets
        for other_user_path in self.user_dir.iterdir():
            if other_user_path.is_dir():
                preset_path = other_user_path / f"{preset_id}.json"
                if preset_path.exists():
                    data = self._read_json(preset_path)
                    preset = Preset.from_dict(data)
                    if user_id in preset.assigned_to:
                        return preset
        
        raise FileNotFoundError(f"Preset {preset_id} not found")
    
    def list_admin_presets(self) -> list[Preset]:
        """List all admin presets (public)."""
        presets = []
        for path in self.admin_dir.glob("*.json"):
            data = self._read_json(path)
            presets.append(Preset.from_dict(data))
        return presets
    
    def list_user_presets(self, user_id: str) -> list[Preset]:
        """List user's own presets + shared presets."""
        presets = []
        
        # Own presets
        user_path = self.user_dir / user_id
        if user_path.exists():
            for path in user_path.glob("*.json"):
                data = self._read_json(path)
                presets.append(Preset.from_dict(data))
        
        # Shared presets
        for other_user_path in self.user_dir.iterdir():
            if other_user_path.is_dir() and other_user_path.name != user_id:
                for path in other_user_path.glob("*.json"):
                    data = self._read_json(path)
                    preset = Preset.from_dict(data)
                    if preset.is_shared and user_id in preset.assigned_to:
                        presets.append(preset)
        
        return presets
    
    def update_preset(self, preset_id: str, preset: Preset, user_id: str) -> None:
        """Update preset. Check creator."""
        existing = self.load_preset(preset_id, user_id)
        if user_id != existing.created_by and not is_admin(user_id):
            raise PresetAccessDenied(f"User {user_id} cannot update preset {preset_id}")
        
        preset.validate()
        preset.updated_at = datetime.now(timezone.utc)
        
        # Re-save to same path
        if existing.is_admin:
            path = self.admin_dir / f"{preset_id}.json"
        else:
            path = self.user_dir / user_id / f"{preset_id}.json"
        
        self._atomic_write(path, preset.to_dict())
    
    def delete_preset(self, preset_id: str, user_id: str) -> None:
        """Delete preset and results."""
        existing = self.load_preset(preset_id, user_id)
        if user_id != existing.created_by and not is_admin(user_id):
            raise PresetAccessDenied(f"User {user_id} cannot delete preset {preset_id}")
        
        # Delete preset file
        if existing.is_admin:
            path = self.admin_dir / f"{preset_id}.json"
        else:
            path = self.user_dir / user_id / f"{preset_id}.json"
        path.unlink()
        
        # Delete results directory
        results_dir = Path.home() / ".usswing" / "screener_results" / f"preset_{preset_id}"
        if results_dir.exists():
            import shutil
            shutil.rmtree(results_dir)
    
    def grant_access(self, preset_id: str, user_ids: list[str], requestor_id: str) -> None:
        """Grant preset access to users."""
        preset = self.load_preset(preset_id, requestor_id)
        if requestor_id != preset.created_by and not is_admin(requestor_id):
            raise PresetAccessDenied()
        
        preset.assigned_to = list(set(preset.assigned_to) | set(user_ids))
        preset.is_shared = True
        self.update_preset(preset_id, preset, requestor_id)
    
    def revoke_access(self, preset_id: str, user_id_to_revoke: str, requestor_id: str) -> None:
        """Revoke preset access."""
        preset = self.load_preset(preset_id, requestor_id)
        if requestor_id != preset.created_by and not is_admin(requestor_id):
            raise PresetAccessDenied()
        
        preset.assigned_to = [uid for uid in preset.assigned_to if uid != user_id_to_revoke]
        self.update_preset(preset_id, preset, requestor_id)
    
    def _atomic_write(self, path: Path, data: dict) -> None:
        """Atomic JSON write: temp file + rename."""
        temp_path = path.with_suffix('.tmp')
        with open(temp_path, 'w') as f:
            json.dump(data, f, indent=2)
        temp_path.replace(path)
    
    def _read_json(self, path: Path) -> dict:
        """Read JSON file."""
        with open(path, 'r') as f:
            return json.load(f)
    
    def migrate_v1_presets(self) -> None:
        """One-time migration of v1 ScreenerConfig to v2 presets."""
        if Path.home().joinpath(".usswing", "v1_migration_done").exists():
            return  # Already migrated
        
        # For each user in DB
        for user in get_all_users():  # From DB
            if 'screener_config' in user.settings_json:
                v1_config = user.settings_json['screener_config']
                
                # Create user preset from v1 config
                preset = Preset(
                    id=f"{user.user_id}_v1_settings",
                    name=f"{user.display_name}'s v1 Settings",
                    preset_type="Composite",
                    groups=[
                        ScreenerGroup(
                            id="v1_filters",
                            logic="AND",
                            screeners=[
                                ScreenerRef(
                                    screener_id="indicator_composite",
                                    screener_type="indicator",
                                    config=v1_config,  # Direct mapping
                                )
                            ]
                        )
                    ],
                    created_by=user.user_id,
                    is_admin=False,
                )
                self.create_preset(preset, user.user_id)
        
        # Create "Legacy v1" admin preset
        legacy_preset = Preset(
            id="legacy_v1_default",
            name="Legacy v1 — Default Config",
            preset_type="Composite",
            groups=[...],
            created_by="admin",
            is_admin=True,
        )
        self.create_preset(legacy_preset, "admin")
        
        # Mark migration done
        Path.home().joinpath(".usswing", "v1_migration_done").touch()
```

---

# FO-SCR-005 — Preset Management & Permissions

## DD-SCR-005.001.D01 — ScreenerScheduler
- **Status:** Approved

**Parent SRDs:** SRD-SCR-004.001 through SRD-SCR-004.006

```python
class ScreenerScheduler:
    """Manages cron scheduling for preset runs."""
    
    def __init__(self, executor: PresetExecutor):
        self.executor = executor
        self.scheduler = APScheduler()
        self.schedule_file = Path.home() / ".usswing" / "screener_schedules.json"
    
    def schedule(self, preset_id: str, user_id: str, cron_expr: str) -> None:
        """Schedule a preset to run on cron."""
        # Validate cron expression
        # Add to scheduler
        # Persist to file
        job_id = f"{preset_id}_{user_id}"
        self.scheduler.add_job(
            self.executor.run_preset,
            trigger=CronTrigger.from_crontab(cron_expr, timezone='US/Eastern'),
            args=(preset_id, user_id, False),
            id=job_id,
            replace_existing=True,
        )
        self._persist_schedule(preset_id, cron_expr)
    
    def unschedule(self, preset_id: str) -> None:
        """Remove scheduled job."""
        job_id = f"{preset_id}_*"
        for job in self.scheduler.get_jobs():
            if job.id.startswith(job_id):
                self.scheduler.remove_job(job.id)
        self._persist_schedule(preset_id, None)  # Remove from file
    
    def get_schedule(self, preset_id: str) -> str:
        """Get cron expression for preset."""
        schedules = self._load_schedules()
        return schedules.get(preset_id, "0 8 * * 1-5")  # Default if not set
    
    def start(self) -> None:
        """Start listening for scheduled times."""
        self._load_persisted_schedules()
        self.scheduler.start()
    
    def _load_persisted_schedules(self) -> None:
        """Load saved schedules and re-register jobs."""
        if self.schedule_file.exists():
            schedules = self._load_schedules()
            for preset_id, cron_expr in schedules.items():
                # Re-register job (without user_id; use wildcard)
                # This is a limitation; improve by storing preset_id + user_id together
                pass
    
    def _persist_schedule(self, preset_id: str, cron_expr: str) -> None:
        """Persist schedule to file (atomic)."""
        schedules = self._load_schedules()
        if cron_expr:
            schedules[preset_id] = cron_expr
        else:
            schedules.pop(preset_id, None)
        
        # Atomic write
        temp_path = self.schedule_file.with_suffix('.tmp')
        with open(temp_path, 'w') as f:
            json.dump(schedules, f, indent=2)
        temp_path.replace(self.schedule_file)
    
    def _load_schedules(self) -> dict:
        """Load cron schedules."""
        if not self.schedule_file.exists():
            return {}
        with open(self.schedule_file, 'r') as f:
            return json.load(f)
```

---

## DD-SCR-005.004.D01 — style_filter Parameter on PresetManager List Methods
- **Status:** Draft

**Parent SRD:** SRD-SCR-005.004

### Method Signatures

```python
def list_admin_presets(
    self, style_filter: str | None = None
) -> list[Preset]: ...

def list_user_presets(
    self, user_id: str, style_filter: str | None = None
) -> list[Preset]: ...
```

### Filter Logic

Extracted into a private helper to avoid duplication:

```python
_VALID_STYLE_FILTERS: frozenset[str] = frozenset({"swing", "day", "position"})

def _apply_style_filter(
    self, presets: list[Preset], style_filter: str | None
) -> list[Preset]:
    if style_filter is None:
        return presets
    if style_filter not in _VALID_STYLE_FILTERS:
        raise ValueError(f"Unknown style_filter: {style_filter!r}")
    return [
        p for p in presets
        if not p.trading_styles or style_filter in p.trading_styles
    ]
```

**Rule:** An empty `trading_styles` list always passes the filter (untagged preset = visible regardless of selected style).

Both `list_admin_presets` and `list_user_presets` call `_apply_style_filter` as their last step, after assembling the full preset list.

---

# FO-SCR-006 — LLM Ranking & Result Persistence

## DD-SCR-006.001.D01 — Result Storage & LLM Integration
- **Status:** Approved

**Parent SRDs:** SRD-SCR-008.001 through SRD-SCR-008.005, SRD-SCR-006.001 through SRD-SCR-006.007

```python
@dataclass
class ScreenerRunResult:
    """Result of a preset execution."""
    preset_id: str
    preset_type: str  # "Composite" or "Weighted"
    run_timestamp: datetime
    execution_mode: str  # "scheduled" or "manual"
    total_symbols_screened: int
    symbols_after_prefilter: int
    passed_count: int
    results: list[dict]  # [{symbol, passed, score, details, ...}]
    execution_times: dict  # {pre_filter_ms, stage2_ms, stage3_ms}
    llm_ranking: dict = None  # Optional ranking results

class ScreenerResultsStorage:
    """Manages file-based result persistence."""
    
    def __init__(self):
        self.results_dir = Path.home() / ".usswing" / "screener_results"
        self.results_dir.mkdir(parents=True, exist_ok=True)
    
    def save_result(self, result: ScreenerRunResult) -> None:
        """Save result to file (atomic)."""
        date_str = result.run_timestamp.strftime("%Y-%m-%d")
        preset_dir = self.results_dir / f"preset_{result.preset_id}"
        preset_dir.mkdir(parents=True, exist_ok=True)
        
        result_path = preset_dir / f"{date_str}.json"
        
        # Atomic write
        data = {
            'preset_id': result.preset_id,
            'preset_type': result.preset_type,
            'run_timestamp': result.run_timestamp.isoformat(),
            'execution_mode': result.execution_mode,
            'total_symbols_screened': result.total_symbols_screened,
            'symbols_after_prefilter': result.symbols_after_prefilter,
            'passed_count': result.passed_count,
            'results': result.results,
            'execution_times': result.execution_times,
            'llm_ranking': result.llm_ranking,
        }
        
        temp_path = result_path.with_suffix('.tmp')
        with open(temp_path, 'w') as f:
            json.dump(data, f, indent=2)
        temp_path.replace(result_path)
    
    def load_result(self, preset_id: str, date: str) -> ScreenerRunResult:
        """Load result from file."""
        result_path = self.results_dir / f"preset_{preset_id}" / f"{date}.json"
        if not result_path.exists():
            raise FileNotFoundError(f"Result not found: {result_path}")
        
        with open(result_path, 'r') as f:
            data = json.load(f)
        
        # Deserialize
        return ScreenerRunResult(
            preset_id=data['preset_id'],
            preset_type=data['preset_type'],
            run_timestamp=datetime.fromisoformat(data['run_timestamp']),
            execution_mode=data['execution_mode'],
            total_symbols_screened=data['total_symbols_screened'],
            symbols_after_prefilter=data['symbols_after_prefilter'],
            passed_count=data['passed_count'],
            results=data['results'],
            execution_times=data['execution_times'],
            llm_ranking=data.get('llm_ranking'),
        )
    
    def list_results(self, preset_id: str, limit: int = 30) -> list[dict]:
        """List recent results for preset."""
        preset_dir = self.results_dir / f"preset_{preset_id}"
        if not preset_dir.exists():
            return []
        
        files = sorted(preset_dir.glob("*.json"), reverse=True)[:limit]
        results = []
        for path in files:
            with open(path, 'r') as f:
                data = json.load(f)
                results.append({
                    'date': path.stem,
                    'passed_count': data['passed_count'],
                    'run_timestamp': data['run_timestamp'],
                })
        return results

class FeatureCache:
    """Caches extracted features per symbol per day (24h TTL)."""
    
    def __init__(self):
        self.cache_dir = Path.home() / ".usswing" / "screener_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def get(self, date: date, symbol: str) -> dict or None:
        """Get cached features (None if expired or missing)."""
        cache_file = self.cache_dir / f"features_{date.isoformat()}.json"
        if not cache_file.exists():
            return None
        
        with open(cache_file, 'r') as f:
            data = json.load(f)
        
        if symbol in data:
            features, timestamp = data[symbol]
            # Check TTL (24 hours)
            age_hours = (datetime.now() - datetime.fromisoformat(timestamp)).total_seconds() / 3600
            if age_hours < 24:
                return features
        
        return None
    
    def set(self, date: date, symbol: str, features: dict) -> None:
        """Cache features."""
        cache_file = self.cache_dir / f"features_{date.isoformat()}.json"
        
        # Load existing or create new
        data = {}
        if cache_file.exists():
            with open(cache_file, 'r') as f:
                data = json.load(f)
        
        # Add/update
        data[symbol] = [features, datetime.now().isoformat()]
        
        # Write atomically
        temp_path = cache_file.with_suffix('.tmp')
        with open(temp_path, 'w') as f:
            json.dump(data, f, indent=2)
        temp_path.replace(cache_file)

class APIUsageTracker:
    """Tracks Claude API usage and costs."""
    
    def __init__(self):
        self.usage_file = Path.home() / ".usswing" / "screener_api_usage.json"
    
    def log_usage(self, preset_id: str, tokens_in: int, tokens_out: int) -> None:
        """Log API call."""
        cost = (tokens_in * 0.003 + tokens_out * 0.009) / 1000  # Sonnet pricing
        
        # Load existing
        usage = self._load_usage()
        
        # Add entry
        entry = {
            'date': datetime.now().isoformat(),
            'preset_id': preset_id,
            'tokens_in': tokens_in,
            'tokens_out': tokens_out,
            'cost_usd': cost,
        }
        usage.append(entry)
        
        # Check monthly threshold
        month_start = datetime.now().replace(day=1)
        month_cost = sum(u['cost_usd'] for u in usage if datetime.fromisoformat(u['date']) >= month_start)
        threshold = 50.0  # Configurable
        if month_cost > threshold:
            logger.warning(f"Monthly API cost exceeded threshold: ${month_cost:.2f} > ${threshold:.2f}")
        
        # Persist
        temp_path = self.usage_file.with_suffix('.tmp')
        with open(temp_path, 'w') as f:
            json.dump(usage, f, indent=2)
        temp_path.replace(self.usage_file)
    
    def _load_usage(self) -> list:
        if not self.usage_file.exists():
            return []
        with open(self.usage_file, 'r') as f:
            return json.load(f)
```

---

# FO-SCR-007 — GUI Preset Builder

## DD-SCR-007.001.D01 — GUI Architecture
- **Status:** Approved

**Parent SRDs:** SRD-SCR-007.001 through SRD-SCR-007.009

- **Screener Panel:** 5th main nav tab (Dashboard · Screener · Execution · Chart · **Screener** · Settings)
- **Preset Selector:** Dropdown (Admin Presets | User Presets | Create New)
- **"Run Now" Button:** Triggers `PresetExecutor.run_preset(preset_id, user_id)`
- **Results Table:** Symbol, Score, Details (collapsible), Optional LLM Rank
- **Preset Builder (Modal):**
  - Drag-and-drop screeners in groups (Composite) or flat (Weighted)
  - Toggle AND/OR logic per group
  - Collapsible config panels per screener
  - Real-time preview
  - Validation on save
- **Historical Results Selector:** Date picker (last 30 days with results)
- **Export CSV:** Download results table to file

---

## DD-SCR-007.010.D01 — Style Filter Dropdown in Screener Panel
- **Status:** Draft

**Parent SRD:** SRD-SCR-007.010

### Widget Placement

`QComboBox` inserted into `ScreenerPanel` layout **above** the preset selector, labelled "Style:".

### Items

| Display Label    | `currentData()` value |
|------------------|-----------------------|
| All Styles       | `None`                |
| Swing Trading    | `"swing"`             |
| Day Trading      | `"day"`               |
| Position Trading | `"position"`          |

### Implementation Sketch

```python
class ScreenerPanel(QWidget):
    def _build_style_filter_combo(self) -> QComboBox:
        combo = QComboBox()
        for label, value in [
            ("All Styles", None),
            ("Swing Trading", "swing"),
            ("Day Trading", "day"),
            ("Position Trading", "position"),
        ]:
            combo.addItem(label, value)
        combo.currentIndexChanged.connect(self._on_style_filter_changed)
        return combo

    def _on_style_filter_changed(self) -> None:
        style_filter: str | None = self._style_combo.currentData()
        admin = self._manager.list_admin_presets(style_filter=style_filter)
        user = self._manager.list_user_presets(self._user_id, style_filter=style_filter)
        self._rebuild_preset_dropdown(admin, user)
```

### State

- Default: index 0 ("All Styles", `style_filter=None`)
- Not persisted across sessions (always resets to "All Styles" on launch)

---

## DD-SCR-007.011.D01 — Trading Style Checkboxes in Preset Builder
- **Status:** Draft

**Parent SRD:** SRD-SCR-007.011

### Widget Structure

`QGroupBox("Trading Style")` with a horizontal `QHBoxLayout` containing three `QCheckBox` widgets.

| Checkbox label   | Internal value |
|------------------|----------------|
| Swing Trading    | `"swing"`      |
| Day Trading      | `"day"`        |
| Position Trading | `"position"`   |

### Implementation Sketch

```python
_STYLE_OPTIONS: list[tuple[str, str]] = [
    ("Swing Trading", "swing"),
    ("Day Trading", "day"),
    ("Position Trading", "position"),
]

class PresetBuilderPanel(QWidget):
    def _build_style_section(self, editable: bool) -> QGroupBox:
        group = QGroupBox("Trading Style")
        layout = QHBoxLayout(group)
        self._style_checks: dict[str, QCheckBox] = {}
        for label, value in _STYLE_OPTIONS:
            cb = QCheckBox(label)
            cb.setEnabled(editable)
            self._style_checks[value] = cb
            layout.addWidget(cb)
        return group

    def _load_trading_styles(self, styles: list[str]) -> None:
        for value, cb in self._style_checks.items():
            cb.setChecked(value in styles)

    def _collect_trading_styles(self) -> list[str]:
        return [v for v, cb in self._style_checks.items() if cb.isChecked()]
```

### Editability Rules

- **Creator / admin:** checkboxes enabled; saved to `preset.trading_styles` on "Save Preset"
- **Non-owner viewer:** checkboxes replaced with read-only `QLabel` badge widgets (rounded, coloured per style)

Changes are collected at save time via `_collect_trading_styles()`, not applied immediately.

---

## DD-SCR-007.012.D01 — Assign Users Tokenized Input in Preset Builder
- **Status:** Draft

**Parent SRD:** SRD-SCR-007.012

### Widget Placement & Visibility

`QGroupBox("Assign Users")` placed below the Trading Style section in `PresetBuilderPanel`.

- Visible only for **user-owned presets** (hidden for admin presets)
- **Creator:** full interactive token input
- **Non-owner viewer:** `assigned_to` rendered as a comma-separated read-only `QLabel`

### Widget Architecture

```
QGroupBox("Assign Users")
  ├── TagArea (QWidget, flow layout) — holds existing user ID tags
  └── QLineEdit (placeholder: "Type user ID and press Enter")
```

Each existing `assigned_to` entry renders as a `_UserTag` widget (label + "×" button).

### Implementation Sketch

```python
class AssignUsersWidget(QWidget):
    def __init__(
        self, preset_id: str, manager: PresetManager, requestor_id: str
    ) -> None:
        super().__init__()
        self._preset_id = preset_id
        self._manager = manager
        self._requestor_id = requestor_id
        self._build_ui()

    def _build_ui(self) -> None:
        self._tag_area = QWidget()
        self._tag_layout = FlowLayout(self._tag_area)
        self._input = QLineEdit()
        self._input.setPlaceholderText("Type user ID and press Enter")
        self._input.returnPressed.connect(self._on_add_user)

    def load_existing(self, user_ids: list[str]) -> None:
        for uid in user_ids:
            self._insert_tag(uid, valid=True)

    def _on_add_user(self) -> None:
        user_id = self._input.text().strip()
        if not user_id:
            return
        try:
            self._manager.grant_access(
                self._preset_id, [user_id], self._requestor_id
            )
            self._insert_tag(user_id, valid=True)
        except (PresetAccessDenied, ValueError):
            self._insert_tag(user_id, valid=False)
        self._input.clear()

    def _on_remove_user(self, user_id: str) -> None:
        self._manager.revoke_access(
            self._preset_id, user_id, self._requestor_id
        )

    def _insert_tag(self, user_id: str, valid: bool) -> None:
        tag = _UserTag(user_id, valid=valid)
        tag.removed.connect(self._on_remove_user)
        self._tag_layout.addWidget(tag)


class _UserTag(QWidget):
    removed: pyqtSignal = pyqtSignal(str)

    def __init__(self, user_id: str, valid: bool) -> None:
        super().__init__()
        # QLabel (user_id) + QPushButton("×")
        # Style: green border if valid, red border + tooltip if invalid
```

### Immediate-Apply Semantics

`grant_access` / `revoke_access` are called **on token add/remove**, not deferred to Save Preset. If the builder is closed without saving other fields, the access changes are already persisted.

### User Validation (MVP)

No live user-ID lookup against a user database. An invalid or unknown user ID receives an error-styled tag (red background, tooltip "Unknown user ID"). Future: validate against user registry.

---

# FO-SCR-008 — Module Architecture

## DD-SCR-008.001.D01 — Module Decomposition Summary
- **Status:** Approved

| Module | Responsibility | Public API |
|---|---|---|
| `screener/preset.py` | Preset dataclass (incl. `trading_styles`), validation, serialization | `Preset`, `ScreenerRef`, `ScreenerGroup` |
| `screener/registry.py` | Screener plugin registry | `ScreenerRegistry` |
| `screener/base.py` | Screener protocol (abstract) | `Screener` (Protocol) |
| `screener/screeners/indicator.py` | Indicator screener (wraps v1 filters) | `IndicatorScreener` |
| `screener/screeners/ml.py` | ML screener stub | `MLScreener` |
| `screener/screeners/llm_claude.py` | Claude LLM ranking screener | `LLMClaudeScreener` |
| `screener/screeners/llm_local.py` | Local LLM screener stub | `LLMLocalScreener` |
| `screener/executor.py` | 3-stage pipeline orchestration | `PresetExecutor` |
| `screener/scheduler.py` | Cron job scheduling | `ScreenerScheduler` |
| `screener/storage.py` | Result persistence + feature cache + API usage | `ScreenerResultsStorage`, `FeatureCache`, `APIUsageTracker` |
| `screener/manager.py` | Preset CRUD + permissions + style filter | `PresetManager` |
| `screener/utils.py` | Shared utilities (pre-filter, parallelization) | `PreFilter`, error classes |
| `screener/gui/screener_panel.py` | Screener Panel tab (incl. style filter dropdown) | `ScreenerPanel` |
| `screener/gui/preset_builder.py` | Preset Builder modal (incl. style checkboxes, assign users) | `PresetBuilderPanel`, `AssignUsersWidget` |

### Module Dependency Graph

```
screener/preset.py
  ← dataclasses, datetime

screener/base.py
  ← typing (Protocol)

screener/registry.py
  ← base.py

screener/screeners/indicator.py
  ← base.py, analysis/indicators.py, data/models.py

screener/screeners/ml.py
  ← base.py

screener/screeners/llm_claude.py
  ← base.py, anthropic SDK

screener/executor.py
  ← preset.py, registry.py, base.py, db/manager.py, storage.py, utils.py, app_service

screener/scheduler.py
  ← executor.py, apscheduler

screener/storage.py
  ← pathlib, json, datetime

screener/manager.py
  ← preset.py, storage.py

screener/utils.py
  ← data/models.py
```

---

# FO-SCR-011 — AI-Assisted Stock Ranking (Phase 1)

## DD-SCR-011.001.D21 — AI Stock Ranking with Tool-Augmented Reasoning (Phase 1)
- **Status:** Approved

**Parent SRDs:** SRD-SCR-013.001 through SRD-SCR-013.008

### Overview

Extends Stage 3 of the existing pipeline.  When `Preset.ai_query` is non-empty, `LLMClaudeScreener.apply()` runs a multi-turn `tool_use` loop instead of the legacy single-shot prompt.  The model is given pre-extracted features for every Stage-2 passing symbol plus access to a `get_candle_data` tool that fetches daily/weekly OHLCV on demand via `CandleToolExecutor`.  The final response is a JSON array of `{symbol, score, reasoning}` records.  Reasoning strings are truncated to ≤ 50 words and surfaced via `screener.last_reasoning`, which `PresetExecutor` merges into `result.results[sym]["ai_reasoning"]`.

### Component Diagram

```
Preset(ai_query, ai_model)
      │
      ▼
PresetExecutor._run_stage3(combined, bars)
      │   builds config = {ai_query, ai_model, db, passing_symbols, top_n}
      ▼
LLMClaudeScreener.apply(symbols, bars, config)
      │   ai_query == ""  ─▶  legacy single-shot path (unchanged)
      │   ai_query != ""  ─▶  multi-turn tool-use loop
      ▼
        ┌──────────────────────────────────────────────────────┐
        │  while stop_reason == "tool_use" and turns < 8:      │
        │    response = anthropic.messages.create(             │
        │        tools=[get_candle_data], system=…, messages)  │
        │    for block in response.content if tool_use:        │
        │       result = CandleToolExecutor.execute(name, in)  │
        │       append assistant + tool_result to messages     │
        │  parse final text as JSON ranking                    │
        │  store reasoning in self.last_reasoning              │
        └──────────────────────────────────────────────────────┘
      │
      ▼
PresetExecutor merges last_reasoning → result.results[sym]["ai_reasoning"]
ScreenerPanel renders 60-char preview + tooltip with full text
```

### Key Decisions

1. **Provider-agnostic tool schema.**  `get_candle_data` input schema (`symbol`, `timeframe ∈ {1d, 1w}`, `lookback_bars ∈ [1, 300]`) is identical for Anthropic `tool_use` and OpenAI/Gemini function calling — Phase 2 can add providers without redesigning the tool.
2. **Per-symbol call cap.**  `CandleToolExecutor` enforces 3 calls/symbol/run.  Excess returns `{"error": "tool_call_cap_exceeded"}` JSON to the model rather than raising — the conversation continues with partial data.
3. **Symbol allowlist.**  Only Stage-2 passing symbols may be inspected.  Tool calls for any other symbol return `{"error": "symbol_not_allowed"}` JSON.  This bounds API cost and prevents the model from drifting outside the screener's universe.
4. **Side-channel reasoning.**  Public `screener.apply()` return type is unchanged (`dict[str, tuple[bool, float]]`); reasoning is exposed via `screener.last_reasoning: dict[str, str]`, read by `PresetExecutor` immediately after the call.  Avoids breaking the `Screener` protocol.
5. **Backward compatibility.**  Empty `ai_query` keeps the legacy single-shot path verbatim.  Existing presets — and existing `RN-SCR-2.0.0` tests — continue to pass without modification.
6. **GUI integration.**  Preset builder gains an "AI Query" `QLineEdit` (height `C.INPUT_H`, max 500 chars) inside the existing Trade Settings group box.  Results table gains an "AI Reasoning" column with 60-char truncated preview and full text in `Qt.ItemDataRole.ToolTipRole` tooltip.  CSV export includes the new column.
7. **Database access.**  `_PresetRunWorker.run()` instantiates `DatabaseManager(f"sqlite:///{candles.db}")` per run and threads it through `PresetExecutor(db=...)` → screener config → `CandleToolExecutor(db, allowed_symbols)`.  No long-lived DB handle on the GUI thread.

### Data Flow Example (10 Stage-2 symbols, 2 tool calls)

```
Turn 1:  user → assistant: features JSON for 10 symbols, query "find bullish breakouts"
Turn 1:  assistant: tool_use(symbol=AAPL, 1d, 90)
         user (tool_result): {bars: [...]}
Turn 2:  assistant: tool_use(symbol=NVDA, 1w, 26)
         user (tool_result): {bars: [...]}
Turn 3:  assistant (end_turn): JSON ranking for all 10 symbols
```

### Trade Plan Fields (SRD-SCR-013.009)

The tool-path system prompt adds `"entry": price, "stop": price, "target": price` to each ranking record and says they are optional. `_parse_ranking()` calls `_plan_from_entry(entry)`, which returns `{entry, stop, target}` only when all three convert to finite floats > 0, else `{}`; non-empty plans go to `self.last_plan[sym]` (reset in `apply()`). `PresetExecutor._apply_stage3` reads `last_plan` the same way as `last_reasoning` (dict check) and adds `"ai_plan"` to `result[sym]` only for symbols that have one. The legacy single-shot path never sets a plan. Direction is not checked here; the GUI computes R:R only for long-shaped plans (stop < entry < target).

### Phase 2/3 Forward Compatibility

- `_apply_with_tools()` is structured so the inner loop can be lifted into a provider-agnostic helper when `OpenAIProvider` / `GeminiProvider` are added.
- The reasoning side-channel (`last_reasoning`) survives orchestration — Phase 3's `AIRankingOrchestrator` can collect per-provider reasoning into `provider_reasoning: dict[str, dict[str, str]]`.

---

# FO-SCR-013 — Indicator Catalogue and Rule-List Screening

## DD-SCR-015.001.D01 — Catalogue, Rule Model and Config Schema
- **Status:** Draft

**Parent SRDs:** SRD-SCR-015.001 through SRD-SCR-015.007, SRD-SCR-015.013, SRD-SCR-015.014

### Package layout

New shared package `src/us_swing/core/indicator_rules/` (same layout as `core/notifications/`: private `_*.py` modules, public API re-exported from `__init__`). No Qt imports; both `screener/` and `gui/` import from here and never from each other.

| File | Holds |
|---|---|
| `_ta.py` | `BarArrays`, `Series` and TA-Lib backed series functions (DD-SCR-015.008.D01) |
| `_catalogue.py` | `Category`, `Condition`, `IndicatorRuleError`, `ParamSpec`, `IndicatorSpec`, `CATALOGUE`, `get_spec()` (Condition lives here to avoid a catalogue↔rules import cycle) |
| `_rules.py` | `Rule`, `default_rule()`, `rules_from_config()`, `rules_to_config()`, `rule_label()`, summaries |
| `_evaluate.py` | `RuleContext`, `evaluate_rule()`, `rs_slope_up()` (DD-SCR-015.009.D01) |

### Data types

```python
class Category(Enum):          # display order = declaration order
    PRICE = "Price"; MOMENTUM = "Momentum"; TREND = "Trend"; VOLATILITY = "Volatility"
    VOLUME = "Volume"; RELATIVE_STRENGTH = "Relative strength"
    FUNDAMENTALS = "Fundamentals"; DIVIDENDS = "Dividends"; OTHERS = "Others"

@dataclass(frozen=True, slots=True)
class ParamSpec:
    key: str; label: str; kind: Literal["int", "float"]
    default: float; min: float; max: float; step: float = 1.0

@dataclass(frozen=True, slots=True)
class IndicatorSpec:
    id: str; name: str; category: Category; description: str
    params: tuple[ParamSpec, ...]
    conditions: tuple[Condition, ...]          # first = default condition
    default_value: float | None; default_to: float | None
    value_min: float; value_max: float; unit: str   # "", "%", "$", "×", "$B"
    compute: Callable[[BarArrays, Mapping[str, float]], Series] | None
    context: Literal["none", "rs", "market_cap"] = "none"
    available: bool = True; unavailable_reason: str = ""

class Condition(Enum):   # value = stored string; .label for GUI
    AT_LEAST="at_least"; AT_MOST="at_most"; BETWEEN="between"
    CROSSES_ABOVE="crosses_above"; CROSSES_BELOW="crosses_below"
    PRICE_ABOVE="price_above"; PRICE_BELOW="price_below"; IS_TRUE="is_true"

@dataclass(frozen=True, slots=True)
class Rule:
    indicator_id: str; condition: Condition
    value: float | None = None; to: float | None = None
    params: Mapping[str, float] = field(default_factory=dict); enabled: bool = True
```

`Series` is a small frozen pair `(value: ndarray, reference: ndarray | None)`; `reference` is the signal line for MACD/PPO crosses.

`Condition` also exposes `label` (GUI text, e.g. "at least"), `needs_value` (false for crosses, price above/below, is true) and `needs_to` (true only for between). Helpers used by the GUI: `get_spec(id)`, `default_rule(spec)` (first condition, catalogue default value/to/params), `params_summary(rule)` (e.g. `12 · 26 · 9`).

### Catalogue — release 1

| id | Name | Category | Params (default) | Conditions | Unit | Compute |
|---|---|---|---|---|---|---|
| `price` | Price | Price | — | between, at least, at most | $ | close |
| `atr_pct` | ATR % | Volatility | period 14 | at least, at most, between | % | `atr / close × 100` |
| `rsi` | RSI | Momentum | period 14 | between, at least, at most | — | Wilder RSI |
| `macd` | MACD | Momentum | fast 12, slow 26, signal 9 | crosses above, crosses below, at least, at most | — | line, ref = signal |
| `macd_hist` | MACD Histogram | Momentum | same | at least, at most, between | — | histogram |
| `macd_signal` | MACD Signal Line | Momentum | same | at least, at most, between | — | signal |
| `ppo` / `ppo_hist` / `ppo_signal` | PPO family | Momentum | fast 12, slow 26, signal 9 | as MACD family | % | PPO via EMA, signal = EMA(PPO, 9) |
| `ema_20` / `ema_50` / `ema_100` / `ema_200` | EMA(N) | Trend | period N | price above, price below | $ | EMA |
| `price_ema_20` / `_50` / `_100` | Price/EMA(N) | Trend | period N | at least, at most, between | % | `close / EMA × 100` |
| `breakout` | Breakout (N-bar high) | Trend | lookback 10 | is true | — | `close[-1] > max(close[-1-N:-1])` (legacy semantics; numpy window, since TA-Lib MAX needs N ≥ 2) |
| `volume_ratio` | Volume ratio | Volume | MA period 10 | at least | × | `vol[-1] / mean(vol[-1-N:-1])` (legacy semantics) |
| `rvol_1d` | RVOL (1 Day) | Volume | lookback 20 | at least | × | same function, 20-day default |
| `rvol_3m` `rvol_5m` `rvol_10m` `stvol_3m` `stvol_5m` `stvol_10m` | RVOL / Short-Term Volume (N Min) | Volume | — | at least | × | `None`, `available=False`, reason "needs intraday data" |
| `rs_index` | RS Index | Relative strength | slope days 63 (0 = off) | at least | percentile | context `rs` |
| `market_cap` | Market Cap | Fundamentals | — | at least, at most, between | $B | context `market_cap` |

Dividends and Others have no entries in release 1; the GUI hides empty categories.

### Config schema v2

```json
{"schema": 2,
 "rules": [{"indicator_id": "rsi", "condition": "between", "value": 30, "to": 70,
            "params": {"period": 14}, "enabled": true}],
 "benchmark_symbol": "SPY"}
```

`rules_from_config(cfg)`:
1. `"rules"` present → parse each entry; missing params filled from catalogue defaults.
2. Otherwise → legacy mapping below from `cfg.get("filters", {})`. An absent section uses the legacy defaults, so `{}` gives the 5 legacy rules on and RS off (same as today's engine).
3. Unknown id or unavailable indicator → `IndicatorRuleError("[Screener] Unknown indicator: …")`.

| Legacy section | Rule |
|---|---|
| `volatility{min_atr_pct}` | `atr_pct` at least `min_atr_pct × 100` (fraction → percent) |
| `rsi{min,max,period}` | `rsi` between min..max, period |
| `range{min_price,max_price}` | `price` between min..max |
| `breakout{lookback}` | `breakout` is true, lookback |
| `volume{min_volume_ratio,ma_period}` | `volume_ratio` at least ratio, period = ma_period |
| `rs_index{rs_min_percentile,rs_slope_days}` | `rs_index` at least percentile, slope_days |

`enabled` is copied; default `True` except `rs_index` (`False`). The legacy dict is never written again — the next save stores schema 2.

### Notes
- **EXE strategy-builder catalogue** (`gui/strategy_builder_dialog.py::_INDICATOR_DATA`, SRD-GUI-013.006) is not merged: it feeds an expression evaluator over `dict[tf, DataFrame]` returning last values. A shared catalogue is tracked as TODO T36.
- **Doc mismatch (record only):** MD-SCR-007.011.M17 names `screener/gui/preset_builder.py`, but the builder lives in `gui/screener_panel.py::_PresetBuilderDialog`.

## DD-SCR-015.008.D01 — Indicator Math
- **Status:** Draft

**Parent SRDs:** SRD-SCR-015.008

- Input `BarArrays(open, high, low, close, volume)` as `float64` numpy arrays, built once per symbol from the bar list.
- `atr` = `talib.ATR(high, low, close, period)` (Wilder). `rsi` = `talib.RSI(close, period)` (Wilder). `ema` = `talib.EMA`. `macd` = `talib.MACD(close, fast, slow, signal)`.
- PPO: `ema_f = EMA(close, fast)`, `ema_s = EMA(close, slow)`, `ppo = (ema_f − ema_s) / ema_s × 100`, `signal = EMA(ppo, signal)`, `hist = ppo − signal` (TA-Lib `PPO` has no signal output).
- **Result change:** ATR (was mean of high − low) and RSI (was simple averages; 50 when short) now use Wilder. Old presets give slightly different symbols; recorded in the RN.

## DD-SCR-015.009.D01 — Rule Evaluation and Screener Integration
- **Status:** Draft

**Parent SRDs:** SRD-SCR-015.009 through SRD-SCR-015.012, SRD-SCR-015.015 through SRD-SCR-015.017

### `evaluate_rule(rule, symbol, arrays, ctx) -> tuple[bool, float | None]`
- Params are clamped to their ParamSpec min–max before computing, so a bad stored value cannot break TA-Lib.
- Last value `v = series.value[-1]`; NaN or too few bars → `(False, None)`.
- at least `v ≥ value`; at most `v ≤ value`; between `value ≤ v ≤ to` (inclusive).
- crosses above `value[-2] ≤ ref[-2] and value[-1] > ref[-1]`; crosses below mirrored.
- price above `close[-1] > v`; price below `close[-1] < v`; is true `v == 1.0`.
- Context `rs`: `v = ctx.rs_ranks[sym]`; passes if `v ≥ value` and, when `slope_days > 0`, the RS line rises over `slope_days` (existing `_rs_slope` logic moves to `_evaluate.py`).
- Context `market_cap`: `v = ctx.market_caps[sym] / 1e9`; missing → fail.

### `IndicatorScreener.apply(symbols, bars, config)`
1. `rules = [r for r in rules_from_config(config) if r.enabled]`.
2. If any rule is `rs_index`: compute RS ranks once (`_compute_rs_ranks`, unchanged) — missing benchmark raises `BenchmarkDataUnavailableError`.
3. `ctx = RuleContext(rs_ranks, market_caps=config.get("market_caps", {}), benchmark_arrays)`.
4. Per symbol: build `BarArrays`; `passed = Σ ok`; result `(passed == n, passed / n)`; `n == 0` → `(True, 1.0)`.

`screen_detailed()` runs the same loop and returns `{rule_label(rule): value}` (short names such as `RSI`, `EMA(50)`), because the GUI Details column already prefixes the full `config_summary()`.

### Executor hand-off
`PresetExecutor._run_stage2` gains a `market_caps` argument and calls `apply(symbols, bars, {**ref.config, "market_caps": caps})`. Other screeners ignore the extra key. `run_preset` already receives `market_caps`.

### Summary text
`rule_summary(rule)` → short label e.g. `RSI 30–70 (14)`, `ATR ≥ 1.0%`, `$5–$5K`, `Breakout 10`, `Vol ≥ 1.0×`, `RS ≥ 70 sl63`, `MACD ↑ signal`, `Price > EMA(50)`. `config_summary(cfg)` joins enabled rules with `"  ·  "`, matching today's Details format.

---

# FO-SCR-014 — Price Action Pattern Catalogue and Rule-List Screening

## DD-SCR-016.001.D01 — Pattern Catalogue, Rule Model and Config Schema
- **Status:** Draft

**Parent SRDs:** SRD-SCR-016.001, .002, .007 through .010, .014

### Package layout

New package `src/us_swing/core/price_patterns/`, same layout as `core/indicator_rules/`. It reuses `ParamSpec`, `BarArrays` and `ema()` from `core.indicator_rules` (an import inside `core/`). No Qt imports.

| File | Holds |
|---|---|
| `_spec.py` | `PatternCategory`, `Direction`, `PatternRuleError`, `PatternSpec` (kept apart so `_candles` / `_breakouts` can build specs without an import cycle) |
| `_candles.py` | TA-Lib candle table and `candle_specs()` factory (DD-SCR-016.003.D01) |
| `_breakouts.py` | 20 detect functions and `breakout_specs()` (DD-SCR-016.005.D01) |
| `_rules.py` | `PatternRule`, `default_pattern_rule()`, `pattern_rules_from_config()`, `pattern_rules_to_config()`, `pattern_settings_summary()`, `pattern_config_summary()` |
| `_evaluate.py` | `evaluate_pattern()` (DD-SCR-016.011.D01) |

### Data types

```python
class PatternCategory(Enum):     # display order = declaration order
    BULLISH_CANDLES = "Bullish candles"; BEARISH_CANDLES = "Bearish candles"
    NEUTRAL_CANDLES = "Neutral candles"; BREAKOUT = "Breakout"; TREND = "Trend"
    VOLATILITY = "Volatility"; CHART_SHAPES = "Chart shapes"

class Direction(Enum): BULLISH = "bullish"; BEARISH = "bearish"; NEUTRAL = "neutral"

Detect = Callable[[BarArrays, Mapping[str, float]], bool]
MinBars = Callable[[Mapping[str, float]], int]

@dataclass(frozen=True, slots=True)
class PatternSpec:
    id: str; name: str; short: str          # short: Details key, no "_" (GUI splits on "_")
    category: PatternCategory; direction: Direction; description: str
    params: tuple[ParamSpec, ...]; min_bars: MinBars; detect: Detect
    available: bool = True; unavailable_reason: str = ""   # same shape as IndicatorSpec for the GUI tree

@dataclass(frozen=True, slots=True)
class PatternRule:
    pattern_id: str; params: Mapping[str, float] = {}; enabled: bool = True
```

`PATTERNS = candle_specs() + breakout_specs()` (47 entries). `get_pattern(id)` raises `PatternRuleError` for unknown ids.

### Config schema v2

```json
{"schema": 2, "threshold": 0.2,
 "rules": [{"pattern_id": "hammer", "params": {"within": 1}, "enabled": true}, ...]}
```

- `pattern_rules_to_config(rules, threshold)` writes all params (filled with defaults) so a round trip is lossless.
- `pattern_rules_from_config(cfg) -> tuple[list[PatternRule], float]`:
  - `"rules"` present → parse each dict. Unknown id, unknown param key, non-numeric value or non-list `rules` → `PatternRuleError`. Missing params take the defaults.
  - otherwise → legacy reader (below).
  - The threshold is `float(cfg.get("threshold", 0.2))`; a non-number raises `PatternRuleError`. The range check stays in the screener (`ScreenerError`, SRD-SCR-016.012).

### Legacy mapping (old `patterns` dict)

| Legacy section | Default on | Rule id | Params kept |
|---|---|---|---|
| `proximity_52w_high` | yes | `proximity_52w_high` | `min_ratio`, `lookback` |
| `volume_breakout` | yes | `volume_breakout` | `lookback`, `vol_multiplier` |
| `nr7_compression` | no | `nr7_compression` | — |
| `ema_pullback` | no | `ema_pullback` | `ema_period` |
| `engulfing` | no | `bullish_engulfing` | — (`within` = 1) |

Missing sections use these defaults, so `{}` gives the old default (2 of 5 on, threshold 0.2). Legacy Engulfing was a custom 2-bar check; TA-Lib `CDLENGULFING` needs 3 bars and may differ on equal open/close prices — recorded in the RN.

### Summary text
- `pattern_settings_summary(rule)` uses the shared `format_param_values(params, values)` helper. It moves out of `indicator_rules._rules.settings_summary`, which keeps the same output. One param → `ParamSpec.display` text (`1-bar window`, `EMA 21`). Several → values joined with ` · `. No params → "".
- `pattern_config_summary(cfg)` → `"PA ≥ 20%  ·  52wHigh  ·  VolBreak"`: the threshold as a whole percent, then each enabled rule's `short`. It returns "" when no rule is enabled or the config cannot be read.

## DD-SCR-016.003.D01 — Candlestick Patterns (TA-Lib)
- **Status:** Draft

**Parent SRDs:** SRD-SCR-016.003, SRD-SCR-016.004

- `signal = talib.CDLxxx(open, high, low, close)` (int array, ±100 or 0), using TA-Lib's default candle settings. There is no extra trend filter.
- Match: `sign` is `+1` (`signal > 0`), `−1` (`signal < 0`) or `0` (`signal != 0`), checked on any of the last `within` bars.
- Param `within` (int, 1–5, default 1, display `{}-bar window`).
- `min_bars = abstract.Function(name).lookback + within`, read once when the module loads.
- One-sided functions return a single sign that does not always match the pattern's direction. For example, `CDLGRAVESTONEDOJI` returns +100, so those entries use `sign = 0`.

| id | Name | Function | sign | Short |
|---|---|---|---|---|
| `hammer` | Hammer | CDLHAMMER | 0 | Hammer |
| `inverted_hammer` | Inverted Hammer | CDLINVERTEDHAMMER | 0 | InvHammer |
| `bullish_engulfing` | Bullish Engulfing | CDLENGULFING | +1 | BullEngulf |
| `piercing_line` | Piercing Line | CDLPIERCING | 0 | Piercing |
| `morning_star` | Morning Star | CDLMORNINGSTAR | 0 | MornStar |
| `morning_doji_star` | Morning Doji Star | CDLMORNINGDOJISTAR | 0 | MornDoji |
| `bullish_harami` | Bullish Harami | CDLHARAMI | +1 | BullHarami |
| `three_white_soldiers` | Three White Soldiers | CDL3WHITESOLDIERS | 0 | 3Soldiers |
| `three_inside_up` | Three Inside Up | CDL3INSIDE | +1 | 3InUp |
| `three_outside_up` | Three Outside Up | CDL3OUTSIDE | +1 | 3OutUp |
| `dragonfly_doji` | Dragonfly Doji | CDLDRAGONFLYDOJI | 0 | Dragonfly |
| `shooting_star` | Shooting Star | CDLSHOOTINGSTAR | 0 | ShootStar |
| `hanging_man` | Hanging Man | CDLHANGINGMAN | 0 | HangMan |
| `bearish_engulfing` | Bearish Engulfing | CDLENGULFING | −1 | BearEngulf |
| `dark_cloud_cover` | Dark Cloud Cover | CDLDARKCLOUDCOVER | 0 | DarkCloud |
| `evening_star` | Evening Star | CDLEVENINGSTAR | 0 | EveStar |
| `evening_doji_star` | Evening Doji Star | CDLEVENINGDOJISTAR | 0 | EveDoji |
| `bearish_harami` | Bearish Harami | CDLHARAMI | −1 | BearHarami |
| `three_black_crows` | Three Black Crows | CDL3BLACKCROWS | 0 | 3Crows |
| `three_inside_down` | Three Inside Down | CDL3INSIDE | −1 | 3InDown |
| `three_outside_down` | Three Outside Down | CDL3OUTSIDE | −1 | 3OutDown |
| `gravestone_doji` | Gravestone Doji | CDLGRAVESTONEDOJI | 0 | Gravestone |
| `doji` | Doji | CDLDOJI | 0 | Doji |
| `spinning_top` | Spinning Top | CDLSPINNINGTOP | 0 | SpinTop |
| `marubozu` | Marubozu | CDLMARUBOZU | 0 | Marubozu |
| `three_methods` | Rising/Falling Three Methods | CDLRISEFALL3METHODS | 0 | 3Methods |
| `kicker` | Kicker | CDLKICKING | 0 | Kicker |

The first 11 rows are Bullish candles, the next 11 are Bearish candles and the last 5 are Neutral candles. Each entry's direction follows its group.

## DD-SCR-016.005.D01 — Breakout, Trend, Volatility and Chart-Shape Patterns
- **Status:** Draft

**Parent SRDs:** SRD-SCR-016.005, SRD-SCR-016.006

**Notation:**
- `O H L C V` are float64 arrays and `[-1]` is the last bar.
- `prior(k)` is the k bars before the last bar, `x[-(k+1):-1]`.
- `rng = H − L`.
- `ema()` is TA-Lib's EMA, except that EMA Pullback uses `_seeded_ema`, seeded from the first close as in legacy `analysis.indicators.ema`, so its results are identical.

| id | Name (category, direction) | Params (default, range) | Match on last bar | min_bars |
|---|---|---|---|---|
| `proximity_52w_high` | Near 52-Week High (Breakout, bull) | `min_ratio` 0.90 (0.50–1.00), `lookback` 252 (20–504) | `C[-1] / max(H[-lookback:]) ≥ min_ratio` (all bars if fewer) | 2 |
| `high_52w_breakout` | 52-Week High Breakout (Breakout, bull) | `lookback` 252 (20–504) | `C[-1] > max(prior(lookback) H)` | lookback + 1 |
| `volume_breakout` | Volume Breakout (Breakout, bull) | `lookback` 20 (5–100), `vol_multiplier` 1.5 (1.0–5.0) | `C[-1] > max(prior H)` and `V[-1] > mean(prior V) × vol_multiplier` | lookback + 1 |
| `gap_up` | Gap Up (Breakout, bull) | `min_gap` 1.0 % (0.1–20) | `L[-1] > H[-2]` and `(O[-1] / H[-2] − 1) × 100 ≥ min_gap` | 2 |
| `pocket_pivot` | Pocket Pivot (Breakout, bull) | `lookback` 10 (5–20), `ema_period` 10 (5–50) | `C[-1] > C[-2]`, `V[-1] >` the largest volume of a down-close day in `prior(lookback)` (0 if none), and `C[-1] ≥ ema(C, ema_period)[-1]` | max(lookback + 2, ema_period) |
| `darvas_box` | Darvas Box Breakout (Breakout, bull) | `box_bars` 20 (10–60), `max_depth` 15 % (3–30) | `top = max(prior H)`, `bottom = min(prior L)`; `(top − bottom) / top × 100 ≤ max_depth` and `C[-1] > top` | box_bars + 1 |
| `bull_flag` | Bull Flag (Breakout, bull) | `pole_bars` 5 (3–20), `min_pole_gain` 10 % (5–50), `flag_bars` 5 (3–20) | The pole runs from bar `s = n − 2 − flag − pole` to `e = s + pole`, with `gain = (C[e] / C[s] − 1) × 100 ≥ min_pole_gain`. The flag is `prior(flag_bars)`, and `min(flag L) ≥ C[e] − 0.5 × (C[e] − C[s])`. Breakout: `C[-1] > max(flag H)`. | pole + flag + 2 |
| `ema_pullback` | EMA Pullback (Trend, bull) | `ema_period` 21 (5–200) | `C[-2] < E[-2]` and `C[-1] ≥ E[-1]` with `E = _seeded_ema` | ema_period + 1 |
| `higher_highs_lows` | Higher Highs & Lows (Trend, bull) | `swing_bars` 5 (2–20), `swings` 3 (2–5) | Split the last `swings × swing_bars` bars into `swings` windows. Each window's `max H` and `min L` must be above the previous window's. | swings × swing_bars |
| `lower_highs_lows` | Lower Highs & Lows (Trend, bear) | same | Mirror of the above (each below the previous) | swings × swing_bars |
| `golden_cross` | Golden Cross (Trend, bull) | `fast` 50 (10–100), `slow` 200 (50–300), `within` 5 (1–20) | `Ef = ema(C, fast)`, `Es = ema(C, slow)`. Some `j` in the last `within` bars has `Ef[j−1] ≤ Es[j−1]` and `Ef[j] > Es[j]`. No match if `fast ≥ slow`. | slow + within |
| `fib_retracement_sell` | Fib Retracement (Sell) (Trend, bear) | `lookback` 60 (20–250), `zone_from` 50 % (20–90), `zone_to` 61.8 % (20–90), `min_move` 10 % (3–50) | In `W = last lookback bars`: `b = argmin L` (not the last bar), `a = argmax H` over bars before `b`, `b − a ≥ 5`, `leg = H[a] − L[b] ≥ H[a] × min_move / 100`. Zone `[L[b] + leg × zone_from, L[b] + leg × zone_to]`. Match when `H[-1] ≥` zone bottom and every close after `b` is `≤` zone top. No match if `zone_from > zone_to`. | lookback |
| `fib_retracement_buy` | Fib Retracement (Buy) (Trend, bull) | same | Mirror: `b = argmax H` (not the last bar), `a = argmin L` before `b`, `leg = H[b] − L[a] ≥ L[a] × min_move / 100`. Zone `[H[b] − leg × zone_to, H[b] − leg × zone_from]`. Match when `L[-1] ≤` zone top and every close after `b` is `≥` zone bottom. | lookback |
| `gap_down` | Gap Down (Trend, bear) | `min_gap` 1.0 % (0.1–20) | `H[-1] < L[-2]` and `(1 − O[-1] / L[-2]) × 100 ≥ min_gap` | 2 |
| `outside_bar` | Outside Bar (Trend, neutral) | — | `H[-1] > H[-2]` and `L[-1] < L[-2]` | 2 |
| `nr7_compression` | NR7 (Volatility, neutral) | — | `rng[-1] == min(rng[-7:])` | 7 |
| `nr4` | NR4 (Volatility, neutral) | — | `rng[-1] == min(rng[-4:])` | 4 |
| `inside_bar` | Inside Bar (Volatility, neutral) | — | `H[-1] < H[-2]` and `L[-1] > L[-2]` | 2 |
| `vcp` | Volatility Contraction (VCP) (Volatility, bull) | `lookback` 60 (30–250), `contractions` 3 (2–4), `final_depth` 10 % (2–20) | Split the last `lookback` bars into `contractions` equal windows, with `depth = (max H − min L) / max H × 100`. Depths must strictly fall and the last must be ≤ `final_depth`. Also needs `mean V(last window) < mean V(first window)` and `C[-1] ≥ max(H[-lookback:]) × (1 − final_depth / 100)`. | lookback |
| `bollinger_squeeze` | Bollinger Squeeze (Volatility, neutral) | `period` 20 (10–50), `lookback` 120 (20–250) | `upper, mid, lower = talib.BBANDS(C, period, 2, 2)`, `w = (upper − lower) / mid`; `w[-1] < min(w[-lookback:-1])` (strict new low, so a flat series never matches; any NaN → no match) | period + lookback − 1 |
| `double_bottom` ⚠ | Double Bottom (Chart shapes, bull) | `lookback` 60 (30–250), `tolerance` 3 % (1–10), `within` 5 (1–20) | In `W = last lookback bars`, `a = argmin L` over the first half and `b = argmin L` over the second half (excluding the last bar). Needs `b − a ≥ 10`, `abs(L[b] / L[a] − 1) × 100 ≤ tolerance`, `neck = max H[a..b] ≥ max(L[a], L[b]) × 1.05`, `C[-1] > neck`, and the first `C > neck` after `b` is in the last `within` bars (SRD-SCR-016.017). | lookback |
| `cup_with_handle` ⚠ | Cup with Handle (Chart shapes, bull) | `lookback` 130 (60–250), `max_depth` 35 % (12–50), `handle_bars` 10 (5–20) | The cup is the `lookback − handle_bars − 1` bars before the handle, and the handle is `prior(handle_bars)`. Take `left = max H` of the cup's first third, `bottom = min L` of the cup, and `right = max H` of the cup's last third. Needs `12 ≤ (left − bottom) / left × 100 ≤ max_depth`, `right ≥ 0.95 × left`, `min(handle L) ≥ right − 0.5 × (right − bottom)`, and `C[-1] > max(handle H)`. | lookback |
| `double_top` ⚠ | Double Top (Chart shapes, bear) | `lookback` 60 (30–250), `tolerance` 3 % (1–10), `within` 5 (1–20) | Mirror of Double Bottom: `a = argmax H` over the first half, `b = argmax H` over the second half (excluding the last bar), `b − a ≥ 10`, `abs(H[b] / H[a] − 1) × 100 ≤ tolerance`, `neck × 1.05 ≤ min(H[a], H[b])` with `neck = min L[a..b]`, `C[-1] < neck`, and the first `C < neck` after `b` is in the last `within` bars. | lookback |
| `double_top_pullback` ⚠ | Double Top Pullback (Chart shapes, bear) | `lookback` 60 (30–250), `tolerance` 3 % (1–10), `within` 10 (2–30), `near` 2 % (0.5–5) | Same top shape and neck. The first `C < neck` after `b` is 1 to `within` bars ago, every close since then is below the neck, and `H[-1] ≥ neck × (1 − near / 100)` — the bounce has reached the broken neck (sell-entry zone). | lookback |

⚠ The chart shapes are rough code checks. They can give false matches, and the RN says so. Each existing pattern keeps its legacy formula exactly.

## DD-SCR-016.011.D01 — Evaluation and Screener Integration
- **Status:** Draft

**Parent SRDs:** SRD-SCR-016.011 through SRD-SCR-016.015

### `evaluate_pattern(rule, arrays) -> bool`
1. `spec = get_pattern(rule.pattern_id)`. Params = defaults updated with `rule.params`, each clamped to its ParamSpec min–max and rounded for `int` kinds.
2. `len(arrays.close) < spec.min_bars(params)` → `False`.
3. `bool(spec.detect(arrays, params))`. A NaN compares as false, so it gives no match.

### `PriceActionScreener.apply(symbols, bars, config)`
1. `rules, threshold = pattern_rules_from_config(config)`; keep only enabled rules (`n` of them).
2. A threshold outside 0–1 raises `ScreenerError` (same message style as today).
3. For each symbol: fewer than 2 bars → left out. Otherwise `arrays = BarArrays.from_bars(bars)`, `m = Σ evaluate_pattern`, `score = m / n` if `n` else `0.0`, and the result is `(score ≥ threshold, round(score, 4))`.
4. One DEBUG log line: `[Screener] Price action screened %d stock(s), %d passed`.

`screen_detailed()` runs the same loop and returns `{spec.short: bool}` for each enabled rule. The GUI Details column already shows bool values as ✔ / ✘.

The registry id stays `price_action`. The module no longer imports `us_swing.analysis.indicators`.

---

## Notes for Implementation

1. **Backward Compatibility:** v1 ScreenerEngine **removed entirely**. No conditional "if v1 else v2" logic.
2. **Error Handling:** All exceptions caught at orchestration level; no silent failures.
3. **Concurrency:** Multiprocessing for CPU, asyncio for I/O. No direct threading for screeners.
4. **Atomic File Operations:** All writes temp → rename to prevent corruption.
5. **Permissions:** Enforced at PresetManager level; every load/update/delete checks `created_by` or `assigned_to`.
6. **Feature Caching:** 24h TTL per symbol per day. Cache auto-cleanup on old files.
7. **LLM Fallback:** All LLM errors (timeout, auth, rate limit) result in graceful fallback (unranked Stage 2 results).
8. **Scheduler Persistence:** Cron expressions saved to JSON; load on app startup.

---

**Status:** Approved

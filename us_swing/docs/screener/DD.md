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

### Phase 2/3 Forward Compatibility

- `_apply_with_tools()` is structured so the inner loop can be lifted into a provider-agnostic helper when `OpenAIProvider` / `GeminiProvider` are added.
- The reasoning side-channel (`last_reasoning`) survives orchestration — Phase 3's `AIRankingOrchestrator` can collect per-provider reasoning into `provider_reasoning: dict[str, dict[str, str]]`.

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

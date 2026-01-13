// Global Config Storage
let GAME_CONFIG = {
    stats: { min: 1, max: 10 },
    multipliers: { min: 0.0, max: 5.0 }
};

const DEFAULT_TERRAIN_TAGS = ["forest", "water", "combat", "scavenge", "cold", "fire", "night"];

document.addEventListener('DOMContentLoaded', async () => {
    // 1. Fetch Config & Resources
    await loadGameConfig();
    loadPresets();
    loadItems(); 
    
    // 2. Initialize UI
    const tributeList = document.getElementById('tributeList');
    if (tributeList.children.length === 0) {
        addTributeRow();
    }
    
    // Default Terrain
    // Initial render acts as if these are "loaded" active tags
    const defaults = {};
    DEFAULT_TERRAIN_TAGS.forEach(t => defaults[t] = 1.0);
    renderTerrainConfig(defaults);

    // --- EVENT DELEGATION ---
    tributeList.addEventListener('click', (e) => {
        const target = e.target;
        
        if (target.matches('.btn-toggle-stats')) {
            const row = target.closest('.tribute-row');
            const panel = row.querySelector('.stats-panel');
            panel.style.display = (panel.style.display === 'none') ? 'block' : 'none';
        }
        
        if (target.matches('.btn-delete-row')) {
            target.closest('.tribute-row').remove();
        }

        if (target.matches('.tag-close')) {
            target.parentElement.remove();
        }
    });

    // Handle Image URL Changes
    tributeList.addEventListener('change', (e) => {
        if (e.target.matches('.t-img')) {
            const input = e.target;
            const img = input.closest('.tribute-row').querySelector('.tribute-avatar');
            const placeholder = input.closest('.tribute-row').querySelector('.avatar-placeholder');
            
            if (input.value) {
                img.src = input.value;
                img.style.display = 'block';
                if(placeholder) placeholder.style.display = 'none';
            } else {
                img.style.display = 'none';
                if(placeholder) placeholder.style.display = 'block';
            }
        }
    });

    // --- ARROW KEY NAVIGATION ---
    tributeList.addEventListener('keydown', (e) => {
        if (e.key === 'ArrowUp' || e.key === 'ArrowDown' || e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
            const target = e.target;
            // Only navigate if we are in an input/select
            if (target.tagName === 'INPUT' || target.tagName === 'SELECT') {
                e.preventDefault();
                const rows = Array.from(document.querySelectorAll('.tribute-row'));
                const selectors = ['.t-name-input', '.t-dist', '.t-gender'];
                const row = target.closest('.tribute-row');
                const selector = selectors.find(cls => target.matches(cls));
                let nextInput = null

                if ((e.key === 'ArrowLeft' || e.key === 'ArrowRight') && selector) {
                    const index = selectors.indexOf(selector)
                    let nextIndex = e.key === 'ArrowRight' ? index + 1 : index - 1;
                    nextIndex = Math.max(Math.min(nextIndex, selectors.length), 0);
                    nextInput = row.querySelector(selectors[nextIndex]);
                } else if ((e.key === 'ArrowUp' || e.key === 'ArrowDown') && row) {
                    const index = rows.indexOf(row);
                    let nextIndex = e.key === 'ArrowDown' ? index + 1 : index - 1;
                    nextIndex = Math.max(Math.min(nextIndex, rows.length), 0);
                    nextInput = rows[nextIndex].querySelector(selector);
                }
                if (!nextInput) return
                nextInput.focus()
                if (nextInput.select) nextInput.select()

            }
        }
    });

    // 3. Static Button Listeners
    document.getElementById('addTributeBtn').addEventListener('click', () => addTributeRow());
    document.getElementById('loadRosterBtn').addEventListener('click', loadRosterHandler);
    document.getElementById('loadTerrainBtn').addEventListener('click', loadTerrainHandler);
    
    // Add Custom Terrain Listener
    document.getElementById('addTerrainBtn').addEventListener('click', addCustomTerrainModifier);

    document.getElementById('saveRosterBtn').addEventListener('click', () => alert("Roster Save not implemented on backend yet."));
    document.getElementById('saveTerrainBtn').addEventListener('click', () => alert("Terrain Save not implemented on backend yet."));

    document.getElementById('setupForm').addEventListener('submit', submitGame);

    // Prevent Enter Submit
    document.getElementById('setupForm').addEventListener('keydown', function(e) {
        if (e.key === 'Enter') {
            if (e.target.tagName !== 'TEXTAREA' && e.target.type !== 'submit' && e.target.type !== 'button') {
                e.preventDefault();
                return false;
            }
        }
    });
});

// --- API & DATA LOADING ---

async function loadGameConfig() {
    try {
        const res = await fetch('/api/config');
        const data = await res.json();
        if (data.status === 'success') {
            GAME_CONFIG = data.data;
        }
    } catch (e) {
        console.warn("Could not load config, using defaults.");
    }
}

async function loadItems() {
    try {
        const res = await fetch('/api/items');
        window.AVAILABLE_ITEMS = (await res.json()).data || [];
    } catch (e) { console.error(e); }
}

async function loadPresets() {
    try {
        const [rRes, tRes] = await Promise.all([
            fetch('/api/rosters'),
            fetch('/api/terrains')
        ]);
        const rData = await rRes.json();
        const tData = await tRes.json();
        
        populateSelect('rosterPreset', rData.data, (p) => `${p.name} (${p.count})`);
        populateSelect('terrainPreset', tData.data, (p) => p.name);
    } catch (e) { console.error(e); }
}

function populateSelect(id, list, textFn) {
    const sel = document.getElementById(id);
    sel.innerHTML = '<option value="" disabled selected>Load Existing...</option>';
    if(list) list.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p.filename;
        opt.textContent = textFn(p);
        sel.appendChild(opt);
    });
}

async function loadRosterHandler() {
    const fname = document.getElementById('rosterPreset').value;
    if(!fname) return;
    try {
        const res = await fetch(`/api/roster/${fname}`);
        const data = await res.json();
        if(data.status === 'success') {
            document.getElementById('tributeList').innerHTML = '';
            if(data.data.preset_name) document.getElementById('rosterName').value = data.data.preset_name;
            data.data.tributes.forEach(t => addTributeRow(t));
        }
    } catch(e) { console.error(e); }
}

async function loadTerrainHandler() {
    const fname = document.getElementById('terrainPreset').value;
    if(!fname) return;
    try {
        const res = await fetch(`/api/terrain/${fname}`);
        const data = await res.json();
        if(data.status === 'success') {
            const t = data.data.data || data.data; 
            const loadedMultipliers = t.tag_multipliers || {};
            renderTerrainConfig(loadedMultipliers);
            document.getElementById('terrainName').value = t.name || "";
        }
    } catch(e) { console.error(e); }
}

function getNextBalancedDistrict() {
    // 1. Scan current inputs into a Frequency Map
    const counts = {}; 
    
    document.querySelectorAll('.t-dist').forEach(input => {
        const val = parseInt(input.value);
        if (!isNaN(val) && val >= 1) {
            counts[val] = (counts[val] || 0) + 1;
        }
    });

    // 2. Find first district (1-12) with < 2 tributes
    for (let i = 1; i <= 12; i++) {
        // If count is undefined (0) or less than 2, return it
        if (!counts[i] || counts[i] < 2) return i;
    }

    // 3. Fallback: If all are full, return the largest++
    const districts = Object.keys(counts).map(Number);
    if (districts.length === 0) return 1;
    return (Math.max(...districts)++);
}

// --- UI GENERATION ---

function addTributeRow(data = null) {
    const container = document.getElementById('tributeList');
    
    // Use Algo for District if new row, otherwise use data
    let defaultDistrict = 12;
    if (!data) {
        defaultDistrict = getNextBalancedDistrict();
    }

    const t = data || {
        name: "", district: defaultDistrict, gender: "N", image_url: "",
        stats: { strength: 5, speed: 5, intel: 5, defense: 5, aggression: 5, stealth: 5 },
        proficient_items: []
    };
    if (!t.stats.stealth) t.stats.stealth = 5;

    const row = document.createElement('div');
    row.className = 'card tribute-row';
    row.style.padding = '10px';
    
    row.innerHTML = `
        <div style="display: flex; gap: 10px; align-items: center; flex-wrap: wrap;">
            <div style="flex: 0 0 50px; height: 50px; background: #333; border-radius: 50%; overflow: hidden; position: relative;">
                <img class="tribute-avatar" src="${t.image_url}" onerror="this.style.display='none'; this.nextElementSibling.style.display='block'" style="width:100%; height:100%; object-fit:cover; display: ${t.image_url ? 'block' : 'none'}">
                <span class="avatar-placeholder" style="display:${t.image_url ? 'none' : 'block'}; font-size:24px; text-align:center; line-height:50px; width: 100%;">👤</span>
            </div>
            
            <input type="text" class="btn t-name-input" placeholder="Name" value="${t.name}" style="border: 1px solid var(--border-color); background: var(--bg-primary); color: var(--text-primary);">
            <input type="number" class="btn t-dist" placeholder="Dist" value="${t.district}" min="1" max="12" style="width: 60px; border: 1px solid var(--border-color); background: var(--bg-primary); color: var(--text-primary);">
            <select class="btn t-gender" style="border: 1px solid var(--border-color); background: var(--bg-primary); color: var(--text-primary);">
                <option value="M" ${t.gender === 'M' ? 'selected' : ''}>M</option>
                <option value="F" ${t.gender === 'F' ? 'selected' : ''}>F</option>
                <option value="N" ${t.gender === 'N' ? 'selected' : ''}>N</option>
            </select>
            
            <button type="button" class="btn btn-toggle-stats" style="background: var(--bg-panel); color: var(--text-primary);">Stats & Items ⚙️</button>
            <button type="button" class="btn btn-delete-row" style="background: #ff4444; color: white;">✕</button>
        </div>
        
        <div class="stats-panel hidden" style="margin-top: 10px; padding-top: 10px; border-top: 1px solid var(--border-color); display: none;">
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                <div>
                    ${generateSlider('Strength', t.stats.strength)}
                    ${generateSlider('Speed', t.stats.speed)}
                    ${generateSlider('Intel', t.stats.intel)}
                    ${generateSlider('Defense', t.stats.defense)}
                    ${generateSlider('Aggression', t.stats.aggression)}
                    ${generateSlider('Stealth', t.stats.stealth)}
                </div>
                <div style="display: flex; flex-direction: column; gap: 10px;">
                    <label style="font-size: 0.8em; color: var(--text-secondary);">Image URL</label>
                    <input type="text" class="btn t-img" placeholder="http://..." value="${t.image_url || ''}" style="width: 100%; background: var(--bg-primary); color: var(--text-primary); border: 1px solid var(--border-color);">
                    
                    <label style="font-size: 0.8em; color: var(--text-secondary);">Proficient Items</label>
                    <div class="tag-container" onclick="this.querySelector('input').focus()">
                        <div class="tags-list"></div>
                        <input type="text" class="tag-input" placeholder="Add item...">
                        <div class="suggestions-list hidden"></div>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    container.appendChild(row);

    // Initialize Tags & Autocomplete
    const tagList = row.querySelector('.tags-list');
    const tagInput = row.querySelector('.tag-input');
    const suggestions = row.querySelector('.suggestions-list');
    
    if (t.proficient_items) t.proficient_items.forEach(item => createTag(item, tagList));

    tagInput.addEventListener('input', () => {
        const val = tagInput.value.toLowerCase();
        suggestions.innerHTML = '';
        if (!val || !window.AVAILABLE_ITEMS) {
            suggestions.classList.add('hidden');
            return;
        }
        
        const matches = window.AVAILABLE_ITEMS.filter(i => i.toLowerCase().includes(val));
        if (matches.length === 0) {
            suggestions.classList.add('hidden');
            return;
        }
        
        suggestions.classList.remove('hidden');
        matches.slice(0, 10).forEach(item => {
            const div = document.createElement('div');
            div.className = 'suggestion-item';
            div.textContent = item;
            div.onclick = (e) => {
                e.stopPropagation();
                createTag(item, tagList);
                tagInput.value = '';
                suggestions.classList.add('hidden');
                tagInput.focus();
            };
            suggestions.appendChild(div);
        });
    });

    // Close suggestions on click away
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.tag-container')) {
            suggestions.classList.add('hidden');
        }
    });

    tagInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault(); 
            e.stopPropagation();
            const val = tagInput.value.trim();
            if (val) {
                createTag(val, tagList);
                tagInput.value = '';
                suggestions.classList.add('hidden');
            }
        }
    });
}

function generateSlider(label, value) {
    const key = label.toLowerCase();
    const min = GAME_CONFIG.stats.min;
    const max = GAME_CONFIG.stats.max;
    
    return `
        <div style="margin-bottom: 8px;">
            <div style="display: flex; justify-content: space-between; font-size: 0.85em; color: var(--text-secondary);">
                <span>${label}</span>
            </div>
            <div class="stat-control">
                <input type="range" class="stat-slider stat-${key}" value="${value}" min="${min}" max="${max}" oninput="this.nextElementSibling.innerText = this.value">
                <span class="stat-value">${value}</span>
            </div>
        </div>
    `;
}

function createTag(text, container) {
    const span = document.createElement('span');
    span.className = 'tag';
    span.innerHTML = `${text} <span class="tag-close">×</span>`;
    container.appendChild(span);
}

// --- TERRAIN LOGIC ---

function renderTerrainConfig(loadedMultipliers) {
    const container = document.getElementById('terrainList');
    container.innerHTML = ''; 
    const min = GAME_CONFIG.multipliers.min;
    const max = GAME_CONFIG.multipliers.max;
    
    // 1. Gather all unique keys (Defaults + Current UI + Loaded)
    const allKeys = new Set(DEFAULT_TERRAIN_TAGS);
    
    // Add whatever was already on screen (custom user additions)
    const currentSliders = document.querySelectorAll('.terrain-mult');
    currentSliders.forEach(s => allKeys.add(s.dataset.tag));
    
    Object.keys(loadedMultipliers).forEach(k => allKeys.add(k));

    allKeys.forEach(tag => {
        let val = 1.0;
        let isDefault = true;

        if (tag in loadedMultipliers && loadedMultipliers[tag] != 1.0) {
            val = loadedMultipliers[tag];
            isDefault = false;
        }

        appendTerrainSlider(container, tag, val, min, max, isDefault);
    });
}

function appendTerrainSlider(container, tag, val, min, max, isDimmed = false) {
    const div = document.createElement('div');
    // Add dimmed class to the wrapper if needed
    const dimClass = isDimmed ? 'dimmed' : '';
    
    div.innerHTML = `
        <div class="${dimClass}" style="margin-bottom: 12px;" onchange="this.classList.remove('dimmed')">
            <div style="display: flex; justify-content: space-between; font-size: 0.9em; margin-bottom: 5px; color: var(--text-secondary);">
                <span style="text-transform: capitalize;">${tag}</span>
            </div>
            <div class="stat-control">
                <input type="range" 
                       class="stat-slider terrain-mult" 
                       data-tag="${tag}" 
                       value="${val}" 
                       min="${min}" 
                       max="${max}" 
                       step="0.1" 
                       oninput="this.nextElementSibling.innerText = parseFloat(this.value).toFixed(1); this.closest('.dimmed')?.classList.remove('dimmed');">
                <span class="stat-value">${Number(val).toFixed(1)}</span>
            </div>
        </div>
    `;
    container.appendChild(div);
}

function addCustomTerrainModifier() {
    const input = document.getElementById('newTerrainTag');
    const tag = input.value.trim().toLowerCase();
    
    if (!tag) return;
    
    // Check if exists
    const existing = document.querySelector(`.terrain-mult[data-tag="${tag}"]`);
    if (existing) {
        alert("Modifier already exists.");
        // Undim it if it was hidden
        existing.closest('.dimmed')?.classList.remove('dimmed');
        return;
    }
    
    const container = document.getElementById('terrainList');
    const min = GAME_CONFIG.multipliers.min;
    const max = GAME_CONFIG.multipliers.max;
    
    appendTerrainSlider(container, tag, 1.0, min, max, false); // Active by default
    input.value = '';
}

async function submitGame(e) {
    e.preventDefault();
    
    const tributes = [];
    document.querySelectorAll('.tribute-row').forEach(row => {
        const tags = [];
        row.querySelectorAll('.tag').forEach(t => tags.push(t.innerText.replace('×', '').trim()));
        
        const getVal = (cls) => {
            const el = row.querySelector(cls);
            return el ? parseInt(el.value) : 5;
        };

        tributes.push({
            name: row.querySelector('.t-name-input').value || "Unknown",
            district: parseInt(row.querySelector('.t-dist').value) || 12,
            gender: row.querySelector('.t-gender').value,
            image_url: row.querySelector('.t-img').value,
            proficient_items: tags,
            stats: {
                strength: getVal('.stat-strength'),
                speed: getVal('.stat-speed'),
                intel: getVal('.stat-intel'),
                defense: getVal('.stat-defense'),
                aggression: getVal('.stat-aggression'),
                stealth: getVal('.stat-stealth')
            }
        });
    });

    if (tributes.length < 2) {
        alert("You need at least 2 tributes to start!");
        return;
    }

    const mults = {};
    document.querySelectorAll('.terrain-mult').forEach(i => mults[i.dataset.tag] = parseFloat(i.value));

    const payload = {
        tributes: tributes,
        terrain: {
            name: document.getElementById('terrainName').value || "Custom",
            tag_multipliers: mults
        }
    };

    const btn = e.target.querySelector('button[type="submit"]');
    const originalText = btn.innerHTML;
    btn.innerHTML = "Generating...";
    btn.disabled = true;

    try {
        const res = await fetch('/api/simulate', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if(data.status === 'success') window.location.href = `/game/${data.data.game_id}`;
        else { 
            alert(data.message); 
            btn.disabled = false; 
            btn.innerHTML = originalText; 
        }
    } catch(err) {
        console.error(err);
        alert("Network Error");
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}
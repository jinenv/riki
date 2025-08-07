# SEIO MVP Gameplay Documentation

## 🎮 Core Gameplay Loop

**SEIO** is a Monster Warlord-inspired Discord RPG focused on **Esprit collection**, **tower progression**, and **idle mechanics**.

---

## 📝 Command Overview

| Command | Function | Cooldown | Resource Cost |
|---------|----------|----------|---------------|
| `s drop` | Pray for 1 ichor | 5 minutes | None |
| `s summon` | Summon Esprit | None | 1 ichor |
| `s climb` | Fight tower boss | None | 1-5+ stamina |
| `s raid` | Collect idle loot | None | None |

---

## 🔄 Gameplay Flow

### 1. **Prayer System** (`s drop`)
- **Gain 1 ichor** every 5 minutes
- **Optional notifications** when prayer is available
- Primary method to obtain summoning currency

### 2. **Esprit Collection** (`s summon`)  
- **Consume 1 ichor** to summon random Esprit
- **Gacha mechanics** with tier-based probabilities
- **Stack system** - multiple copies combine automatically
- **Fusion progression** - combine copies to increase tier/power

### 3. **Tower Combat** (`s climb`)
- **Monster Warlord-style combat** against floor bosses
- **Flexible stamina usage**: 1 stamina = 1 attack, 5 stamina = 5 attacks, etc.
- **Progression gated** by combat power vs floor difficulty
- **Advance to next floor** upon boss defeat

### 4. **Idle Progression** (`s raid`)
- **Time-based loot generation** since last raid
- **Rewards scale** with current floor and time away
- **Interactive embeds** with button-based reward collection
- **Progress bar** toward next floor unlock (based on total power)

---

## 💰 Currency System

### **Ichor** 🩸
- **Primary source**: Prayer command (5-minute intervals)
- **Primary use**: Esprit summoning
- **Mechanics**: Time-gated resource generation

### **Seios** 🪙  
- **Primary source**: Tower raiding, loot generation
- **Primary use**: Esprit fusion, upgrades, purchases
- **Mechanics**: Main progression currency

### **Erythl** 💎
- **Primary source**: Premium/rare loot drops
- **Primary use**: Acceleration, boosts, advantages
- **Mechanics**: Premium currency for convenience

---

## ⚔️ Combat System

### **Monster Warlord-Style Mechanics**
- **Variable stamina consumption** for strategic depth
- **Power scaling** determines damage output
- **Boss difficulty** scales with floor number
- **Success based** on player total power vs floor requirements

### **Strategic Elements**
- **Resource management** - stamina vs damage output
- **Power optimization** - collection and fusion strategies
- **Timing decisions** - when to climb vs when to raid

---

## 📈 Progression Paths

### **Short-term Loop** (5-30 minutes)
1. Pray for ichor → Summon Esprits → Gain power
2. Climb tower → Defeat boss → Advance floor  
3. Raid for loot → Gain seios → Fuse Esprits

### **Medium-term Goals** (Days/Weeks)
- **Floor progression** through increasingly difficult tower levels
- **Esprit optimization** via fusion and tier advancement
- **Power scaling** to access higher floors and better loot

### **Long-term Progression** (Weeks/Months)  
- **Complete collection** of high-tier Esprits
- **Floor mastery** reaching endgame tower levels
- **Strategic optimization** for maximum efficiency

---

## 🎯 Design Philosophy

### **Monster Warlord DNA**
- **Collection focus** with meaningful progression
- **Strategic resource management** over mindless clicking
- **Social-friendly** Discord-native design
- **Respectful time gates** that encourage return visits

### **MVP Scope**
- **Core loop completeness** - all essential mechanics present
- **Balanced complexity** - deep enough for strategy, simple enough for accessibility  
- **Interactive engagement** - rich Discord embed experiences
- **Scalable foundation** - ready for future feature expansion
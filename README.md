# Fusion 360 Geometric Pattern Add-In

A lightweight, standalone Autodesk Fusion 360 Add-in that replicates the **Geometric Pattern** tool from the Product Design Extension. Create brand-appropriate vent patterns, perforations, and variable-density geometric distributions directly on any planar face without an expensive extension subscription.

---

## ✨ Features

- **Face Selection**: Select any planar face on a solid body.
- **Variable Size Gradient**:
  - **Size Limit 1 & 2**: Set maximum and minimum feature sizes.
  - **Spread Factor**: Non-linear distribution slider (`-1.00` to `+1.00`) controlling gradient falloff.
  - **Gradient Modes**: Radial (Center-out), U-Axis, or V-Axis.
- **Multiple Distribution Types**:
  - **Triangular (Staggered)**: 60° offset row pattern (standard for aesthetic vents).
  - **Rectangular (Grid)**: Uniform orthogonal grid.
  - **Hexagonal**: Honeycomb layout.
  - **Radial**: Concentric circular rings.
- **Precision Alignment**:
  - **U Alignment**: Left, Center, Right.
  - **V Alignment**: Bottom, Center, Top.
- **Boundary Clearance**:
  - **Clear Perimeter**: Prevents features from clipping over external edges or interior cutouts.
  - **Margin**: Custom clearance offset from boundaries.
- **Flexible Operations**:
  - **Cut**: Automatically extrudes vent holes into the body.
  - **Join**: Creates extruded bosses from the face.
  - **New Body**: Extrudes individual solid bodies.
  - **Sketch Only**: Retains 2D sketch curves for downstream modeling.
- **Real-Time Viewport Preview**:
  - Instant `CustomGraphics` preview rendering that dynamically updates without cluttering the design timeline.

---

## 🚀 Installation

### macOS (One-Line Setup)
Run the following command in Terminal to link the add-in into your Fusion 360 AddIns directory:

```bash
ln -s "$(pwd)" "$HOME/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns/GeometricPattern"
```

### Windows
1. Press `Win + R`, paste:
   ```
   %appdata%\Autodesk\Autodesk Fusion 360\API\AddIns
   ```
   and press **Enter**.
2. Copy or link this repository folder into that directory as `GeometricPattern`.

---

## 🎯 How to Use

1. In Fusion 360, open **UTILITIES > Scripts and Add-Ins** (shortcut: `Shift + S`).
2. Under the **Add-Ins** tab, find **GeometricPattern** and click **Run** (check **Run on Startup** for convenience).
3. Switch to **SOLID > CREATE** and click **Geometric Pattern**.
4. Configure your pattern:
   - Select a planar face.
   - Adjust **Size Limit 1**, **Size Limit 2**, **Spread**, and **Distance**.
   - Select your preferred **Distribution Type** and **Alignment**.
   - Check **Clear Perimeter** to keep holes inside face boundaries.
   - Set **Operation** to **Cut** (or **Join** / **New Body** / **Sketch Only**).
5. Watch the real-time preview in the viewport, then click **OK**.

---

## 🧪 Testing

Run the unit test suite:
```bash
python3 -m unittest discover tests
```

---

## 📄 License

MIT License. Free for personal and commercial use.

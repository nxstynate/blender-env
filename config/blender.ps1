$source = "$HOME/pro-env/files/blender/Blender/"
$target = "$env:APPDATA/Blender Foundation/Blender"

# Check if something exists at the target path
if (Test-Path $target)
{
    $existing = Get-Item $target -Force
    if ($existing.Attributes -band [IO.FileAttributes]::ReparsePoint)
    {
        Write-Host "🔗 Existing symbolic link found at: $target — removing it."
    } else
    {
        Write-Host "Null"
    }
    if (Test-Path $target)
    {
        Remove-Item -Path $target -Recurse -Force
    }
}

# Try to create symbolic link first
try
{
    New-Item -ItemType SymbolicLink -Path $target -Target $source -Force -ErrorAction Stop
    Write-Host "✅ Created symbolic link at: $target"
    Write-Host "   → Points to: $source"
} catch
{
    Write-Host "⚠️ Unable to create symbolic link (likely insufficient permissions)"
    Write-Host "   Error: $($_.Exception.Message)"
    Write-Host "🔄 Falling back to copying files instead..."
    
    try
    {
        # Copy files instead
        Copy-Item -Path $source -Destination $target -Recurse -Force -ErrorAction Stop
        Write-Host "✅ Successfully copied files to: $target"
        Write-Host "   ⚠️ NOTE: Changes will NOT sync automatically. You'll need to manually update."
    } catch
    {
        Write-Host "❌ Failed to copy files: $($_.Exception.Message)"
        exit 1
    }
}

# Verify the setup
Write-Host "`n🔍 Verification:"
if (Test-Path $target)
{
    $item = Get-Item $target -Force
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)
    {
        Write-Host "   Type: Symbolic Link ✅"
        Write-Host "   Target: $($item.Target)"
    } else
    {
        Write-Host "   Type: Regular Directory (Copy) 📁"
        Write-Host "   Size: $((Get-ChildItem $target -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB) MB"
    }
} else
{
    Write-Host "   ❌ Target path not found!"
}

# Script to make blender startup in full screen.
Copy-Item "$HOME/pro-env/files/blender/startupScripts/fullscreen_startup.py" "$HOME/programs/Blender4.5/4.5/scripts/startup/."

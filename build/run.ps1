<#
  micropod build harness (Docker Desktop; Windows PowerShell or PowerShell Core).
  -Mode is mandatory; -Tag selects targets (each tag = one image, all by default):
  alpine-arm64, alpine-armv7, debian-arm64, debian-armv7, debian-armv5.

    .\build\run.ps1 -Mode build                   # build base image(s) + verify
    .\build\run.ps1 -Mode build -Tag debian-armv5 # a subset
    .\build\run.ps1 -Mode tar                     # package built images -> device tars
    .\build\run.ps1 -Mode cleanup                 # remove all micropod images

  Prereq: Docker Desktop running. Two privileged side-effects:
    - for an armv5 tag, -Mode build first runs `tonistiigi/binfmt --install all`
      to register full QEMU binfmt (Docker Desktop drops it on each restart);
    - -Mode tar runs quay.io/podman/stable (pulled on first use) to rewrite the
      tar into RouterOS' legacy docker-archive format.
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory)][ValidateSet('build','tar','cleanup')][string]$Mode,
  [string[]]$Tag = @('alpine-arm64','alpine-armv7','debian-arm64','debian-armv7','debian-armv5')
)

# ===========================================================================
# Tuning — parallelism (edit here)
#   $BuildParallel : concurrent image builds       (build phase 1)
#   $TestParallel  : concurrent boot+verify runs    (build phase 2)
# Verify timing is load-sensitive; keep $TestParallel low (1 = sequential,
# most accurate graceful-stop measurement).
# ===========================================================================
$BuildParallel = [Environment]::ProcessorCount
$TestParallel  = [int][Math]::Ceiling([Environment]::ProcessorCount / 2)

# 'Continue' (not 'Stop'): native-command stderr (e.g. docker's platform
# warning) must not be turned into a terminating error. We check $LASTEXITCODE
# explicitly and `throw` on real failures.
$ErrorActionPreference = 'Continue'
$repo = Split-Path -Parent $PSScriptRoot
$out  = Join-Path $PSScriptRoot 'out'
New-Item -ItemType Directory -Force -Path $out | Out-Null

# tag -> dockerfile, buildx platform. The key is the image tag (micropod:<key>).
$map = @{
  'alpine-arm64' = @{ df = 'Dockerfile.alpine'; plat = 'linux/arm64'  }
  'alpine-armv7' = @{ df = 'Dockerfile.alpine'; plat = 'linux/arm/v7' }
  'debian-arm64' = @{ df = 'Dockerfile.debian'; plat = 'linux/arm64'  }
  'debian-armv7' = @{ df = 'Dockerfile.debian'; plat = 'linux/arm/v7' }
  'debian-armv5' = @{ df = 'Dockerfile.debian'; plat = 'linux/arm/v5' }
}

$tags = $Tag | Where-Object {
  if ($map.ContainsKey($_)) { $true } else { Write-Host "skip unknown tag: $_"; $false }
}

# Throttle: block until fewer than $limit of the given jobs are still Running.
function Wait-Slot([System.Collections.IEnumerable]$jobs, [int]$limit) {
  while (@($jobs | Where-Object { $_.State -eq 'Running' }).Count -ge $limit) {
    Start-Sleep -Milliseconds 200
  }
}

$script:results = @()   # set by build mode; drives the exit code

# ===========================================================================
# build — build the base image per tag, then boot it (with a bind-mounted probe
# service) and verify. The base image is kept; nothing else is created.
# ===========================================================================
function Invoke-Build {
  # armv5 needs full QEMU binfmt; Docker Desktop loses the registration on every
  # restart, so register automatically whenever the armv5 tag is in play. The
  # install is idempotent — re-running is cheap.
  if ($tags -contains 'debian-armv5') {
    Write-Host '==> registering QEMU binfmt (qemu-arm covers armv5/v6/v7)'
    docker run --privileged --rm tonistiigi/binfmt --install all
  }

  foreach ($t in $tags) {                            # fresh logs + stale probe dirs
    Remove-Item (Join-Path $out "micropod-$t.log") -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force (Join-Path $out "sv-$t") -ErrorAction SilentlyContinue
  }

  $script:buildJobs = @()
  $script:testJobs  = @()
  $completed = $false

  # Interrupt/abnormal-exit cleanup: kill lingering jobs, remove any container we
  # started and any probe dir. The base images are intentionally kept.
  $cleanup = {
    foreach ($j in @($script:buildJobs) + @($script:testJobs)) {
      if ($j) {
        Stop-Job   -Job $j -ErrorAction SilentlyContinue
        Remove-Job -Job $j -Force -ErrorAction SilentlyContinue
      }
    }
    foreach ($t in $tags) {
      docker rm -f "mptest-$t" *>$null
      Remove-Item -Recurse -Force (Join-Path $out "sv-$t") -ErrorAction SilentlyContinue
    }
  }

  try {
    # -----------------------------------------------------------------------
    # Phase 1 — build. Parallel, throttled to $BuildParallel. Each job streams
    # its build output to build/out/micropod-<tag>.log (UTF-8) so a broken build
    # is debuggable without interleaving every tag's live log on console.
    # -----------------------------------------------------------------------
    $buildScript = {
      param($tag, $c, $repo, $out)
      $base    = "micropod:$tag"
      $logName = "micropod-$tag.log"
      $logFile = Join-Path $out $logName
      try {
        Add-Content -Path $logFile -Encoding utf8 -Value @(
          "==> [$tag] docker buildx build base ($base)",
          "    docker buildx build --platform $($c.plat) -f $($c.df) --provenance=false --sbom=false --load -t $base"
        )
        docker buildx build --platform $c.plat -f (Join-Path $repo $c.df) -t $base `
          --provenance=false --sbom=false --load $repo 2>&1 | Add-Content -Path $logFile -Encoding utf8
        if ($LASTEXITCODE -ne 0) { throw "base build failed (see $logName)" }

        [pscustomobject]@{ Tag = $tag; BuildOk = $true;  Notes = "log=$logName" }
      }
      catch {
        Add-Content -Path $logFile -Encoding utf8 -Value "`n!! $($_.Exception.Message)"
        [pscustomobject]@{ Tag = $tag; BuildOk = $false; Notes = "log=$logName; $($_.Exception.Message)" }
      }
    }

    Write-Host "==> Phase 1: building $(@($tags).Count) image(s), up to $BuildParallel in parallel..."
    foreach ($t in $tags) {
      Wait-Slot $script:buildJobs $BuildParallel
      $script:buildJobs += Start-Job -ScriptBlock $buildScript -ArgumentList $t, $map[$t], $repo, $out
    }
    $script:buildJobs | Wait-Job | Out-Null
    $buildByTag = @{}
    $script:buildJobs | Receive-Job | ForEach-Object { $buildByTag[$_.Tag] = $_ }
    $script:buildJobs | Remove-Job
    $script:buildJobs = @()

    # -----------------------------------------------------------------------
    # Phase 2 — boot + verify. Parallel, throttled to $TestParallel. Boots the
    # base image with a generated `hello` service bind-mounted (rw, so s6 can
    # write its supervise/event state) under a per-tag probe dir. Timing checks
    # are load-sensitive (see header) — $TestParallel = 1 is cleanest.
    # -----------------------------------------------------------------------
    $testScript = {
      param($tag, $c, $out)
      $base  = "micropod:$tag"
      $name  = "mptest-$tag"
      $svc   = Join-Path $out "sv-$tag\hello"      # bind-mounted at /etc/s6/sv/hello
      $ok    = $true
      $notes = @("log=micropod-$tag.log")
      try {
        New-Item -ItemType Directory -Force -Path $svc | Out-Null
        [IO.File]::WriteAllText((Join-Path $svc 'run'),
          "#!/bin/sh`necho `"micropod: hello started`"`nexec tail -f /dev/null`n")

        docker rm -f $name *>$null
        docker run -d --platform $c.plat --name $name -v "${svc}:/etc/s6/sv/hello" $base *>$null
        if ($LASTEXITCODE -ne 0) { throw 'docker run failed' }
        Start-Sleep -Seconds 4
        $logs = docker logs $name 2>&1 | Out-String   # 2>&1: fold container stderr into $logs, else it surfaces as NativeCommandError noise
        $top  = docker top $name  | Out-String
        $sec  = (Measure-Command { docker stop -t 10 $name }).TotalSeconds
        docker rm -f $name *>$null

        if ($logs -notmatch 'micropod: hello started') { $ok = $false; $notes += 'no service log' }
        if ($top  -notmatch 's6-svscan')               { $ok = $false; $notes += 'no s6-svscan' }
        if ($top  -notmatch 's6-supervise')            { $ok = $false; $notes += 'no s6-supervise' }
        if ($sec  -ge 9)                               { $ok = $false; $notes += "slow stop ${sec}s (not graceful)" }
        else { $notes += "stop=$([math]::Round($sec,1))s" }
      }
      catch {
        $ok = $false
        $notes += $_.Exception.Message
      }
      Remove-Item -Recurse -Force (Split-Path $svc -Parent) -ErrorAction SilentlyContinue
      $res = if ($ok) { 'PASS' } else { 'FAIL' }
      [pscustomobject]@{ Tag = $tag; Result = $res; Notes = ($notes -join '; ') }
    }

    Write-Host "==> Phase 2: verifying, up to $TestParallel in parallel..."
    $resultByTag = @{}
    foreach ($t in $tags) {
      $b = $buildByTag[$t]
      if (-not $b -or -not $b.BuildOk) {     # build failed: no point booting it
        $bn = if ($b) { $b.Notes } else { $null }
        $resultByTag[$t] = [pscustomobject]@{ Tag = $t; Result = 'FAIL'; Notes = $bn }
        continue
      }
      Wait-Slot $script:testJobs $TestParallel
      $script:testJobs += Start-Job -ScriptBlock $testScript -ArgumentList $t, $map[$t], $out
    }
    if ($script:testJobs) {
      $script:testJobs | Wait-Job | Out-Null
      $script:testJobs | Receive-Job | ForEach-Object { $resultByTag[$_.Tag] = $_ }
      $script:testJobs | Remove-Job
      $script:testJobs = @()
    }
    $script:results = foreach ($t in $tags) { $resultByTag[$t] }

    "`n=== Summary ==="
    $script:results | Select-Object Tag, Result, Notes | Format-Table -AutoSize -Wrap
    Write-Host "logs: $out   (base images kept; run -Mode tar to package, -Mode cleanup to remove)"
    $completed = $true
  }
  finally {
    if (-not $completed) {
      Write-Host "`n!! interrupted — cleaning up jobs, containers and probe dirs..."
      & $cleanup
    }
  }
}

# ===========================================================================
# tar — package existing base images into the legacy docker-archive tar
# RouterOS needs (see header). docker save -> OCI tar, podman rewrites -> legacy.
# ===========================================================================
function Invoke-Tar {
  $have = New-Object 'System.Collections.Generic.HashSet[string]'
  docker image ls --format '{{.Repository}}:{{.Tag}}' | ForEach-Object { [void]$have.Add($_) }

  $okTags = foreach ($t in $tags) {
    if ($have.Contains("micropod:$t")) { $t }
    else { Write-Host "skip (no image micropod:$t — run -Mode build first): $t" }
  }
  if (-not $okTags) { Write-Host '==> nothing to package.'; return }

  Write-Host "==> docker save $(@($okTags).Count) base image(s) -> OCI tar(s)..."
  foreach ($t in $okTags) {
    Remove-Item (Join-Path $out "micropod-$t.tar") -ErrorAction SilentlyContinue
    $oci = Join-Path $out "micropod-$t.oci.tar"
    docker save "micropod:$t" -o $oci
    if ($LASTEXITCODE -ne 0) { Write-Host "!! docker save failed: micropod:$t" }
  }

  # podman's docker-archive writer emits <id>/layer.tar + repositories
  # (uncompressed); run it under Docker (privileged + vfs, pulls
  # quay.io/podman/stable once). docker save loaded it as docker.io/library/...
  Write-Host "==> converting to RouterOS legacy format via podman..."
  $conv = ($okTags | ForEach-Object {
    "podman load -i /out/micropod-$($_).oci.tar >/dev/null; podman save --format docker-archive -o /out/micropod-$($_).tar docker.io/library/micropod:$($_) >/dev/null; echo converted-micropod-$($_).tar"
  }) -join '; '
  docker run --rm --privileged -e STORAGE_DRIVER=vfs -v "${out}:/out" quay.io/podman/stable bash -c "set -e; $conv"
  if ($LASTEXITCODE -ne 0) { Write-Host '!! podman conversion failed — device tars may be missing or still OCI-format' }
  foreach ($t in $okTags) { Remove-Item (Join-Path $out "micropod-$t.oci.tar") -ErrorAction SilentlyContinue }
  Write-Host "tars: $out"
}

# ===========================================================================
# cleanup — remove ALL micropod:* images.
# ===========================================================================
function Invoke-CleanupImages {
  $imgs = docker image ls --format '{{.Repository}}:{{.Tag}}' |
    Where-Object { $_ -match '^micropod:' }
  if (-not $imgs) { Write-Host '==> no micropod images to remove.'; return }
  Write-Host "==> removing $(@($imgs).Count) image(s)..."
  foreach ($img in $imgs) { docker image rm $img *>$null; Write-Host "    rm $img" }
}

switch ($Mode) {
  'build'   { Invoke-Build }
  'tar'     { Invoke-Tar }
  'cleanup' { Invoke-CleanupImages }
}

if ($script:results -and ($script:results.Result -contains 'FAIL')) { exit 1 } else { exit 0 }

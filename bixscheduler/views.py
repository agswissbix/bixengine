from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from datetime import datetime, timedelta
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_q.models import Schedule
from django_q.tasks import async_task
from bixscheduler.utils import get_available_tasks
from rest_framework.decorators import api_view

HOOK_PATH = 'bixscheduler.hooks.on_task_success'
FUNC_PATH = 'bixscheduler.tasks.'

@api_view(['POST'])
@login_required(login_url='/login/')
def toggle_scheduler(request):
    schedule_id = request.data.get('id')
    if not schedule_id:
        return JsonResponse({"error": "Missing schedule id"}, status=400)

    schedule = Schedule.objects.filter(id=schedule_id).first()
    if not schedule:
        return JsonResponse({"error": "Schedule not found"}, status=404)

    if schedule.next_run is None:
        now = timezone.now()
        schedule.next_run = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
    else:
        schedule.next_run = None
    schedule.save()
    return JsonResponse({"success": True, "next_run": schedule.next_run})



@api_view(['POST'])
@login_required(login_url='/login/')
def run_scheduler_now(request):
    schedule_id = request.data.get('id')
    if not schedule_id:
        return JsonResponse({"error": "Missing schedule id"}, status=400)

    schedule = Schedule.objects.filter(id=schedule_id).first()
    if not schedule:
        return JsonResponse({"error": "Schedule not found"}, status=404)

    try:
        async_task(schedule.func, hook=schedule.hook or HOOK_PATH)
        return JsonResponse({"success": True})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)

@api_view(['POST'])
@login_required(login_url='/login/')
def delete_scheduler(request):
    schedule_id = request.data.get('id')
    if not schedule_id:
        return JsonResponse({"error": "Missing schedule id"}, status=400)

    schedule = Schedule.objects.filter(id=schedule_id).first()
    if not schedule:
        return JsonResponse({"error": "Schedule not found"}, status=404)

    schedule.delete()
    return JsonResponse({"success": True})


@login_required(login_url='/login/')
def lista_schedule_get(request):
    schedules = Schedule.objects.all().order_by('id')
    for s in schedules:
        restart_schedule(s)

    available_tasks = get_available_tasks()
    data = []
    for s in schedules:
        data.append({
            "id": s.id,
            "name": s.name,
            "func": s.func,
            "schedule_type": s.schedule_type,
            "minutes": s.minutes,
            "next_run": s.next_run,
            "display_next_run": getattr(s, "display_next_run", None),
            "repeats": s.repeats,
            "hook": s.hook
        })

    return JsonResponse({"schedules": data, "available_tasks": available_tasks})


@api_view(['POST'])
@login_required(login_url='/login/')
def lista_schedule_post(request):
    schedule_data = request.data.get('schedule')
    if not schedule_data:
        return JsonResponse({"error": "Missing schedule data"}, status=400)

    schedule_id = schedule_data.get('id')
    schedule_obj = get_object_or_404(Schedule, id=schedule_id)

    # Aggiorna campi base
    schedule_obj.name = schedule_data.get('name', "")
    schedule_obj.func = schedule_data.get('func')
    schedule_obj.schedule_type = schedule_data.get('schedule_type')
    schedule_obj.hook = HOOK_PATH

    # Gestione minuti
    if schedule_obj.schedule_type == 'I':
        minutes = schedule_data.get('minutes')
        schedule_obj.minutes = int(minutes) if minutes else None
    else:
        schedule_obj.minutes = None

    # Gestione ripetizioni
    repeats = schedule_data.get('repeats')
    if schedule_obj.schedule_type != 'O':
        if repeats == -1:
            schedule_obj.repeats = -1
        else:
            try:
                schedule_obj.repeats = int(repeats)
            except (TypeError, ValueError):
                schedule_obj.repeats = 1
    else:
        schedule_obj.repeats = 1

    # Gestione next_run
    from django.utils.dateparse import parse_datetime
    next_run_str = schedule_data.get('next_run')
    if next_run_str:
        dt = parse_datetime(next_run_str)
        if dt:
            schedule_obj.next_run = dt - timedelta(hours=2)

    schedule_obj.save()
    return JsonResponse({"success": True})




def restart_schedule(schedule):
    now, ref, stype = timezone.now(), schedule.next_run, schedule.schedule_type
    if not ref:
        schedule.display_next_run = None
        return
    if ref > now:
        schedule.display_next_run = ref + timedelta(hours=2)
        return
    if schedule.repeats == 0:
        schedule.next_run = None
        schedule.save(update_fields=['next_run'])
        schedule.display_next_run = None
        return

    if stype == 'H':
        next_run = now.replace(minute=ref.minute, second=0, microsecond=0)
        if next_run <= now: next_run += timedelta(hours=1)
    elif stype == 'D':
        next_run = now.replace(hour=ref.hour, minute=ref.minute, second=0, microsecond=0)
        if next_run <= now: next_run += timedelta(days=1)
    elif stype == 'W':
        days = (ref.weekday() - now.weekday()) % 7
        next_run = now.replace(hour=ref.hour, minute=ref.minute, second=0, microsecond=0) + timedelta(days=days)
        if next_run <= now: next_run += timedelta(days=7)
    elif stype == 'M':
        from calendar import monthrange
        y, m, d = now.year, now.month, ref.day
        try:
            next_run = now.replace(day=d, hour=ref.hour, minute=ref.minute, second=0, microsecond=0)
        except ValueError:
            next_run = now.replace(day=monthrange(y, m)[1], hour=ref.hour, minute=ref.minute, second=0, microsecond=0)
        if next_run <= now:
            m, y = (m + 1, y + 1) if m == 12 else (m + 1, y)
            next_run = next_run.replace(year=y, month=m, day=min(d, monthrange(y, m)[1]))
    elif stype == 'I':
        interval = schedule.minutes or 1
        passed = int((now - ref).total_seconds() // (interval * 60)) + 1
        next_run = ref + timedelta(minutes=interval * passed)
    else:
        next_run = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)

    schedule.next_run = next_run
    schedule.save(update_fields=['next_run'])
    schedule.display_next_run = next_run + timedelta(hours=2)


@login_required(login_url='/login/')
def aggiungi_scheduler(request):
    if request.method != 'POST':
        return JsonResponse({"error": "Method not allowed"}, status=405)

    now = timezone.now()
    next_run_default = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)

    Schedule.objects.create(
        name='Nuovo Scheduler',
        func=f"{FUNC_PATH}aggiorna_cache",
        hook=HOOK_PATH,
        schedule_type='O',
        minutes=None,
        next_run=next_run_default,
        repeats=1,
    )
    return JsonResponse({"success": True})

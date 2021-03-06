from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .forms import ImageCreateForm
from .models import Image
from common.decorators import ajax_required
from actions.utils import create_action
import redis
from django.conf import settings

r = redis.StrictRedis(host=settings.REDIS_HOST,
                      port=settings.REDIS_PORT,
                      db=settings.REDIS_DB)

@login_required
def image_create(request):
    '''ОБРАБОТЧИК СОХРАНЕНИЯ КАРТИНКИ В БД'''
    
    if request.method == 'POST':
        # форма отправлена
        form = ImageCreateForm(data=request.POST)
        if form.is_valid():
            # валидация формы
            cd = form.cleaned_data
            new_item = form.save(commit=False)

            # добавляем текущего пользователя
            new_item.user = request.user
            new_item.save()
            create_action(request.user, 'добавил изображение', new_item)
            messages.success(request, 'Изображение успешно добавлено')

            return redirect(new_item.get_absolute_url())
    else:
        form = ImageCreateForm(data=request.GET)

    return render(request,
                  'images/image/create.html',
                  {'section': 'images',
                   'form': form})

@ajax_required
@login_required
@require_POST
def image_like(request):
    '''ОБРАБОТЧИК ЛАЙКОВ'''

    image_id = request.POST.get('id')
    action = request.POST.get('action')
    if image_id and action:
        try:
            image = Image.objects.get(id=image_id)
            if action == 'like':
                image.users_like.add(request.user)
                create_action(request.user, 'лайкнул', image)
            elif action == 'unlike':
                image.users_like.remove(request.user)
            return JsonResponse({'status':'ok'})
        except:
            pass
    return JsonResponse({'status':'ko'})



def image_detail(request, id, slug):
    '''ОБРАБОТЧИК ПРОСМОТРА ДЕТАЛЕЙ КАРТИНКИ'''

    image = get_object_or_404(Image, id=id, slug=slug)
    total_views = r.incr('image:{}:views'.format(image.id)) # Инкрементируем кол-во просмотров
    r.zincrby('image_ranking', image.id, 1) # Инкрементируем рейтинг картинки
    return render(request,
                  'images/image/detail.html',
                  {'section': 'images',
                   'image': image,
                   'total_views': total_views})



@login_required
def image_list(request):
    '''ОБРАБОТЧИК СПИСКА КАРТИНОК'''

    images = Image.objects.all()
    paginator = Paginator(images, 8)
    page = request.GET.get('page')
    try:
        images = paginator.page(page)
    except PageNotAnInteger:
        # Если переданная страница не является числом, возвращаем первую
        images = paginator.page(1)
    except EmptyPage:
        if request.is_ajax():
            # Если получили AJAX запрос с номером страницы, большим, чем их кол-во
            # возвращаем пустую страницу
            return HttpResponse('')
        # Если номер страницы больше, чем их кол-во, возвращаем последнюю
        images = paginator.page(paginator.num_pages)
    if request.is_ajax():
        return render(request, 'images/image/list_ajax.html',
                      {'section': 'images', 'images': images})
    return render(request, 'images/image/list.html',
                  {'section': 'images', 'images': images})


@login_required
def image_ranking(request):
    '''ОБРАБОТЧИК РЕЙТИНГА ПРОСМОТРОВ НА REDIS'''
    # Получаем множество рейтинга картинок
    image_ranking = r.zrange('image_ranking', 0, -1, desc=True)[:10]
    image_ranking_ids = [int(id) for id in image_ranking]

    # Получаем отсортированный список самых популярных пикч
    most_viewed = list(Image.objects.filter(id__in=image_ranking_ids))
    most_viewed.sort(key = lambda x: image_ranking_ids.index(x.id))
    return render(request,
                  'images/image/ranking.html',
                  {'section': 'images',
                   'most_viewed': most_viewed})




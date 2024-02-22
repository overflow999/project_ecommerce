from django.shortcuts import render,redirect
from core.forms import *
from django.contrib import messages
from core.models import *
from django.utils import timezone
from django.conf import settings
from django.http import HttpResponse

from django.shortcuts import get_object_or_404
import razorpay
razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_ID,settings.RAZORPAY_SECRET))
# Create your views here.
def index(request):
    products = Product.objects.all()
    return render(request,'core/index.html',{'products':products})

def orderlist(request): 
    if Order.objects.filter(user=request.user,ordered=False).exists():
        order = Order.objects.get(user=request.user,ordered=False)
        return render(request,'core/orderlist.html',{'order':order})      
    return render(request,'core/orderlist.html',{'message':"Your Cart Is Empty"})   

def add_product(request):
    if request.method == 'POST':
        form = ProductForm(request.POST,request.FILES)
        if form.is_valid():
            print("True")
            form.save()
            print("Data saved")
            messages.success(request,"Product Added")
            return redirect('/')

        else:
         print("Not Working")
         messages.info(request,"Product Not Added,Try Again")

    else:
        form = ProductForm()
    return render(request,'core/add_product.html',{'form':form})    

def product_desc(request,pk):
    product = Product.objects.get(pk=pk)
    return render(request,'core/product_desc.html',{'product':product})

def add_to_cart(request,pk):
    product = Product.objects.get(pk=pk)
    order_item,created = OrderItem.objects.get_or_create(
        product = product,
        user = request.user,
        ordered = False
    )
    # get query set of order objectnof particular user
    order_qs = Order.objects.filter(user=request.user,ordered=False)
    if order_qs.exists():
        order = order_qs[0]
        if order.items.filter(product__pk=pk).exists():
            order_item.quantity +=1
            order_item.save()
            messages.info(request,"Added Quantity Item")
            return redirect("/",pk=pk)
        else:
            order.items.add(order_item)
            messages.info(request,"Item Added To cart")
            return redirect("product_desc",pk=pk)

    else:
        ordered_date = timezone.now()
        order = Order.objects.create(user=request.user,ordered_date = ordered_date)
        order.items.add(order_item)
        messages.info(request,"Item Added To cart")
        return redirect("/")
   




def add_item(request,pk):
    product = Product.objects.get(pk=pk)
    order_item,created = OrderItem.objects.get_or_create(
        product = product,
        user = request.user,
        ordered = False,
    )
    # get query set of order objectnof particular user
    order_qs = Order.objects.filter(user=request.user,ordered=False)
    if order_qs.exists():
        order = order_qs[0]
        if order.items.filter(product__pk=pk).exists():
            if order_item.quantity < product.product_available_count:
                order_item.quantity +=1
                order_item.save()
                messages.info(request,"Added Quantity Item")
                return redirect("orderlist")
            else:
                messages.info(request,"No more of this product in stock")
                return redirect("orderlist")

        else:
            order.items.add(order_item)
            messages.info(request,"Item Added To cart")
            return redirect("product_desc",pk=pk)

    else:
        ordered_date = timezone.now()
        order = Order.objects.create(user=request.user,ordered_date = ordered_date)
        order.items.add(order_item)
        messages.info(request,"Item Added To cart")
        return redirect("product_desc",pk=pk)

def remove_item(request,pk):
    item = get_object_or_404(Product,pk=pk)
    order_qs = Order.objects.filter(
        user = request.user,
        ordered = False,
    )
    if order_qs.exists():
        order = order_qs[0]
        if order.items.filter(product__pk=pk).exists():
            order_item = OrderItem.objects.filter(
                product = item,
                user = request.user,
                ordered = False,
            )[0]
            if order_item.quantity > 1:
                order_item.quantity -= 1
                order_item.save()
            else:
                order_item.delete()
            messages.info(request," Item Quantity was updated")
            return redirect("orderlist")
        else:
             messages.info(request," This Item is not in your cart")
             return redirect("orderlist")
    else:
         messages.info(request,"You Don't have any order")
         return redirect("orderlist")
    

def checkout_address(request):
    if CheckoutAddress.objects.filter(user=request.user).exists():
        return render(request,'core/checkout_address.html',{'payment_allow':'allow'})
    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid:
                street_address = request.POST.get('street_address')
                apartment_address = request.POST.get('apartment_address')
                country = request.POST.get('country')
                zip_code = request.POST.get('zip_code')

                checkout_address = CheckoutAddress(
                    user=request.user,
                    street_address=street_address,
                    apartment_address=apartment_address,
                    country=country,
                    zip_code=zip_code
                )
                checkout_address.save()
                print("saved")
                return render(request,'core/checkout_address.html',{'payment_allow':'allow'})
        else:
            messages.warning(request,'failed checkout')
            return redirect('checkout_address')
    else:
        form = CheckoutForm()
        return render(request,'core/checkout_address.html',{'form':form})

def payment(request):
    try:
        order =  Order.objects.get(user=request.user,ordered=False)
        address = CheckoutAddress.objects.get(user=request.user)
        order_amount = order.get_total_price()
        order_currency = "INR"
        order_receipt = order.order_id
        notes = {
            'street_address': address.street_address,
            'apartment_address':address.apartment_address,
            'country':address.country.name,
            'zip':address.zip_code,
        }

        razorpay_order = razorpay_client.order.create(dict(
            amount = order_amount * 100,
            currency = order_currency,
            receipt = order_receipt,
            notes = notes,
            payment_capture = "0",
        ))
        print(razorpay_order["id"])
        order.razorpay_order_id = razorpay_order["id"]
        order.save()
        print("it should render the summary page")
        return render(request,"core/paymentsummary.html",{
            'order':order,
            'order_id': razorpay_order["id"],
            'orderId':order.order_id,
            'final_price': order_amount,
            'razorpay_merchant_id':settings.RAZORPAY_ID,
        })
    except Order.DoesNotExist:
        print("order not found")
        return HttpResponse("404 Error")

def handlerequest(request):
    if request.method == 'POST':
        try:
            payment_id = request.POST.get('razorpay_payment_id',"")
            order_id = request.POST.get('razorpay_order_id',"")
            signature = request.POST.get('razorpay_signature_id',"")
            print(payment_id, order_id,signature)
            params_dict = {
                "razorpay_order_id": order_id,
                "razorpay_payment_id": payment_id,
                "razorpay_signature": signature,
            }
            try:
                order_db = Order.objects.get(razorpay_order_id = order_id)
                print("order found")
            except:
                print("order not found")
                return HttpResponse("SOS Not found")
            order_db.razorpay_payment_id = payment_id
            order_db.razorpay_signature = signature
            order_db.save()
            print("working...")
            result = razorpay_client.utility.verify_payment_signature(params_dict)
            if result == None:
                print("working final fine..")
                amount = order_db.get_total_price()
                amount = amount*100
                payment_status = razorpay_client.payment.capture(payment_id,amount)
                if payment_status is not None:
                    print(payment_status)
                    order_db.ordered = True
                    order_db.save()
                    print("paument success")
                    request.session[
                        "order_complete"
                    ] = "your order has been placed successfully"
                    return render(request,'invoice.html')
                else:
                    print('payment failed')
                    order_db.ordered = False
                    order_db.save()
                    request.session[
                        "order failed"
                    ] ="your order could not be placed"
                    return redirect("/")
            else:
                    order_db.ordered =False
                    order_db.save()
                    return render(requst,"paymentfailed.html")
        except:
                return HttpResponse("Error Occurred")
